import argparse
import base64
import hashlib
import os
import re
import sys
from decimal import Decimal
from pathlib import Path


DEPS_DIR = os.environ.get("MIGRATION_DEPS")
if DEPS_DIR:
    sys.path.insert(0, DEPS_DIR)

import mysql.connector


ROOT = Path(__file__).resolve().parent.parent
TARGET_TABLES = {
    "admin_users",
    "dataset",
    "data_review",
    "hasil_evaluasi_svm",
    "model_artifact",
    "proses_analisis_svm",
    "proses_preprocessing",
}
INSERT_PATTERN = re.compile(
    r"INSERT\s+INTO\s+`(?P<table>[a-zA-Z0-9_]+)`\s*"
    r"\((?P<columns>[^)]+)\)\s+VALUES\s*",
    re.IGNORECASE,
)

SCHEMA = [
    """
    CREATE TABLE admin_users (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE dataset (
        id_dataset INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        id_admin INT NULL,
        nama_dataset VARCHAR(150) NOT NULL,
        status ENUM('aktif','arsip') NOT NULL DEFAULT 'aktif',
        waktu TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        KEY fk_dataset_admin (id_admin),
        CONSTRAINT fk_dataset_admin FOREIGN KEY (id_admin)
            REFERENCES admin_users (id) ON DELETE SET NULL ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE proses_preprocessing (
        id_preprocessing INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        id_dataset INT NOT NULL,
        total_sebelum INT NOT NULL DEFAULT 0,
        total_sesudah INT NOT NULL DEFAULT 0,
        per_platform_sebelum TEXT NULL,
        per_platform_sesudah TEXT NULL,
        waktu TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        KEY fk_preprocessing_dataset (id_dataset),
        CONSTRAINT fk_preprocessing_dataset FOREIGN KEY (id_dataset)
            REFERENCES dataset (id_dataset) ON DELETE CASCADE ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE proses_analisis_svm (
        id_analisis INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        id_dataset INT NOT NULL,
        id_preprocessing INT NOT NULL,
        konfigurasi TEXT NULL,
        waktu TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        KEY fk_analisis_dataset (id_dataset),
        KEY fk_analisis_preprocessing (id_preprocessing),
        CONSTRAINT fk_analisis_dataset FOREIGN KEY (id_dataset)
            REFERENCES dataset (id_dataset) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT fk_analisis_preprocessing FOREIGN KEY (id_preprocessing)
            REFERENCES proses_preprocessing (id_preprocessing) ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE data_review (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        id_dataset INT NOT NULL,
        id_preprocessing INT NULL,
        id_analisis INT NULL,
        teks_review TEXT NOT NULL,
        sumber VARCHAR(50) DEFAULT '-',
        tanggal_komentar VARCHAR(50) NULL,
        tanggal TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        hasil_preprocessing TEXT NULL,
        sentimen VARCHAR(20) NULL,
        status_kelayakan ENUM('baru','layak','tidak_layak') NOT NULL DEFAULT 'baru',
        alasan_kelayakan VARCHAR(100) NULL,
        KEY idx_review_dataset_status (id_dataset, status_kelayakan),
        KEY idx_review_preprocessing (id_preprocessing),
        KEY idx_review_analisis (id_analisis),
        CONSTRAINT fk_review_dataset FOREIGN KEY (id_dataset)
            REFERENCES dataset (id_dataset) ON UPDATE CASCADE,
        CONSTRAINT fk_review_preprocessing FOREIGN KEY (id_preprocessing)
            REFERENCES proses_preprocessing (id_preprocessing) ON DELETE SET NULL ON UPDATE CASCADE,
        CONSTRAINT fk_review_analisis FOREIGN KEY (id_analisis)
            REFERENCES proses_analisis_svm (id_analisis) ON DELETE SET NULL ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE hasil_evaluasi_svm (
        id_evaluasi INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        id_analisis INT NOT NULL UNIQUE,
        total_data INT NOT NULL,
        total_training INT NOT NULL,
        total_testing INT NOT NULL,
        akurasi DECIMAL(6,2) NOT NULL,
        pos_pos INT NOT NULL,
        pos_neg INT NOT NULL,
        pos_net INT NOT NULL,
        neg_pos INT NOT NULL,
        neg_neg INT NOT NULL,
        neg_net INT NOT NULL,
        net_pos INT NOT NULL,
        net_neg INT NOT NULL,
        net_net INT NOT NULL,
        waktu TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_evaluasi_analisis FOREIGN KEY (id_analisis)
            REFERENCES proses_analisis_svm (id_analisis) ON DELETE CASCADE ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE model_artifact (
        id TINYINT NOT NULL PRIMARY KEY,
        artifact LONGBLOB NOT NULL,
        metadata_json JSON NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def connection():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "defaultdb"),
        charset="utf8mb4",
        ssl_disabled=False,
        ssl_ca=str(ROOT / "certs" / "aiven-ca.pem"),
        ssl_verify_cert=True,
        connection_timeout=20,
    )


def hash_password(password, iterations=310000):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${iterations}${encode(salt)}${encode(digest)}"


def _unescape_mysql(value):
    escapes = {
        "0": "\0", "b": "\b", "n": "\n", "r": "\r", "t": "\t",
        "Z": "\x1a", "\\": "\\", "'": "'", '"': '"',
    }
    result = []
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            index += 1
            result.append(escapes.get(value[index], value[index]))
        else:
            result.append(value[index])
        index += 1
    return "".join(result)


def _decode_value(token):
    token = token.strip()
    if token.upper() == "NULL":
        return None
    if len(token) >= 2 and token[0] == "'" and token[-1] == "'":
        return _unescape_mysql(token[1:-1])
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if re.fullmatch(r"-?\d+\.\d+", token):
        return Decimal(token)
    return token


def _split_fields(tuple_text):
    fields = []
    start = 0
    in_quote = False
    escaped = False
    for index, char in enumerate(tuple_text):
        if escaped:
            escaped = False
        elif char == "\\" and in_quote:
            escaped = True
        elif char == "'":
            in_quote = not in_quote
        elif char == "," and not in_quote:
            fields.append(_decode_value(tuple_text[start:index]))
            start = index + 1
    fields.append(_decode_value(tuple_text[start:]))
    return tuple(fields)


def _parse_rows(values_text):
    rows = []
    index = 0
    while index < len(values_text):
        while index < len(values_text) and values_text[index] in " \t\r\n,":
            index += 1
        if index >= len(values_text):
            break
        if values_text[index] != "(":
            raise ValueError(f"Tuple SQL tidak valid pada posisi {index}")
        start = index + 1
        index += 1
        in_quote = False
        escaped = False
        while index < len(values_text):
            char = values_text[index]
            if escaped:
                escaped = False
            elif char == "\\" and in_quote:
                escaped = True
            elif char == "'":
                in_quote = not in_quote
            elif char == ")" and not in_quote:
                rows.append(_split_fields(values_text[start:index]))
                index += 1
                break
            index += 1
        else:
            raise ValueError("Tuple SQL tidak ditutup.")
    return rows


def _iter_inserts(sql_text):
    position = 0
    while True:
        match = INSERT_PATTERN.search(sql_text, position)
        if not match:
            return
        index = match.end()
        in_quote = False
        escaped = False
        while index < len(sql_text):
            char = sql_text[index]
            if escaped:
                escaped = False
            elif char == "\\" and in_quote:
                escaped = True
            elif char == "'":
                in_quote = not in_quote
            elif char == ";" and not in_quote:
                columns = [item.strip().strip("`") for item in match.group("columns").split(",")]
                yield match.group("table"), columns, _parse_rows(sql_text[match.end():index])
                position = index + 1
                break
            index += 1
        else:
            raise ValueError("Pernyataan INSERT tidak ditutup.")


def _load_active_data():
    sql_text = (ROOT / "database" / "analisis_svm_relasi.sql").read_text(encoding="utf-8")
    parsed = {}
    columns = {}
    active_dataset_id = None

    for table, table_columns, rows in _iter_inserts(sql_text):
        if table not in TARGET_TABLES:
            continue
        columns[table] = table_columns
        if table == "dataset":
            status_index = table_columns.index("status")
            id_index = table_columns.index("id_dataset")
            active_rows = [row for row in rows if row[status_index] == "aktif"]
            if active_rows:
                active_dataset_id = max(int(row[id_index]) for row in active_rows)
                parsed[table] = [row for row in active_rows if int(row[id_index]) == active_dataset_id]
        elif table == "data_review":
            if active_dataset_id is None:
                raise RuntimeError("Dataset aktif belum ditemukan sebelum data_review.")
            dataset_index = table_columns.index("id_dataset")
            parsed.setdefault(table, []).extend(
                row for row in rows if int(row[dataset_index]) == active_dataset_id
            )
        else:
            parsed.setdefault(table, []).extend(rows)

    if active_dataset_id is None:
        raise RuntimeError("Dataset aktif tidak ditemukan di dump SQL.")

    for table in ("proses_preprocessing", "proses_analisis_svm"):
        dataset_index = columns[table].index("id_dataset")
        parsed[table] = [row for row in parsed[table] if int(row[dataset_index]) == active_dataset_id]

    analysis_ids = {
        int(row[columns["proses_analisis_svm"].index("id_analisis")])
        for row in parsed["proses_analisis_svm"]
    }
    evaluation_analysis_index = columns["hasil_evaluasi_svm"].index("id_analisis")
    parsed["hasil_evaluasi_svm"] = [
        row for row in parsed["hasil_evaluasi_svm"]
        if int(row[evaluation_analysis_index]) in analysis_ids
    ]

    admin_id = int(parsed["dataset"][0][columns["dataset"].index("id_admin")])
    admin_index = columns["admin_users"].index("id")
    parsed["admin_users"] = [row for row in parsed["admin_users"] if int(row[admin_index]) == admin_id]
    return active_dataset_id, columns, parsed


def _insert_rows(cursor, table, columns, rows, batch_size=500):
    if not rows:
        return
    names = ", ".join(f"`{name}`" for name in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    query = f"INSERT INTO `{table}` ({names}) VALUES ({placeholders})"
    for start in range(0, len(rows), batch_size):
        cursor.executemany(query, rows[start:start + batch_size])


def inspect_database(db):
    cursor = db.cursor()
    try:
        cursor.execute("SHOW TABLES")
        tables = sorted(row[0] for row in cursor.fetchall())
        print("tables=" + ",".join(tables))
    finally:
        cursor.close()


def reset_partial(db):
    cursor = db.cursor()
    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in sorted(TARGET_TABLES):
            cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        db.commit()
        print("reset=ok")
    finally:
        cursor.close()


def migrate(db):
    active_dataset_id, columns, parsed = _load_active_data()
    cursor = db.cursor()
    try:
        cursor.execute("SHOW TABLES")
        existing = {row[0] for row in cursor.fetchall()}
        conflict = existing & TARGET_TABLES
        if conflict:
            raise RuntimeError("Migrasi dibatalkan karena tabel target sudah ada: " + ", ".join(sorted(conflict)))

        for statement in SCHEMA:
            cursor.execute(statement)

        admin_rows = [list(row) for row in parsed["admin_users"]]
        password_index = columns["admin_users"].index("password")
        admin_rows[0][password_index] = hash_password(os.environ["ADMIN_PASSWORD"])
        parsed["admin_users"] = [tuple(row) for row in admin_rows]

        for table in (
            "admin_users", "dataset", "proses_preprocessing",
            "proses_analisis_svm", "data_review", "hasil_evaluasi_svm",
        ):
            _insert_rows(cursor, table, columns[table], parsed[table])

        artifact = (ROOT / "model" / "model_sentimen.joblib").read_bytes()
        cursor.execute("INSERT INTO model_artifact (id, artifact) VALUES (1, %s)", (artifact,))
        db.commit()

        cursor.execute("SELECT COUNT(*) FROM data_review")
        total_review = int(cursor.fetchone()[0])
        cursor.execute(
            "SELECT COUNT(*) FROM data_review WHERE status_kelayakan = 'layak' "
            "AND hasil_preprocessing IS NOT NULL"
        )
        total_layak = int(cursor.fetchone()[0])
        print(
            f"migration=ok dataset={active_dataset_id} "
            f"reviews={total_review} preprocessed={total_layak} models=1"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--reset-partial", action="store_true")
    args = parser.parse_args()
    db = connection()
    try:
        if args.check:
            inspect_database(db)
        elif args.reset_partial:
            reset_partial(db)
        else:
            migrate(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
