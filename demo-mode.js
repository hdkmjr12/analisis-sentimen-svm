(function () {
    'use strict';

    const isLandingPage = /(?:^|\/)index\.html$/i.test(window.location.pathname)
        || /analisis-sentimen-svm\/?$/i.test(window.location.pathname);

    // GitHub Pages tidak memiliki backend. Halaman selain landing page dibuka
    // sebagai admin demo supaya seluruh navigasi dan tampilan penelitian terlihat.
    if (!isLandingPage) {
        localStorage.setItem('role_akses', 'admin');
        localStorage.setItem('id_admin', '1');
    }

    const distribution = [
        ['Youtube', 'POSITIF', 859],
        ['Youtube', 'NEGATIF', 249],
        ['Youtube', 'NETRAL', 622],
        ['Tiktok', 'POSITIF', 603],
        ['Tiktok', 'NEGATIF', 73],
        ['Tiktok', 'NETRAL', 488],
        ['Instagram', 'POSITIF', 98],
        ['Instagram', 'NEGATIF', 23],
        ['Instagram', 'NETRAL', 81]
    ];

    const sampleText = {
        POSITIF: [
            'Mobil LCGC nyaman dipakai harian, hemat bahan bakar, dan biaya perawatannya terjangkau.',
            'Saya puas menggunakan mobil ini untuk kebutuhan keluarga dan perjalanan sehari-hari.',
            'Desainnya menarik, irit, serta cocok sebagai mobil pertama.'
        ],
        NEGATIF: [
            'Suspensinya terasa keras dan kabin kurang nyaman ketika melewati jalan yang rusak.',
            'Fitur keselamatan dan kualitas material masih perlu ditingkatkan.',
            'Tarikan mobil terasa kurang bertenaga saat membawa banyak penumpang.'
        ],
        NETRAL: [
            'Mobil ini digunakan untuk perjalanan dari rumah ke tempat kerja.',
            'Pilihan kendaraan disesuaikan dengan kebutuhan dan anggaran keluarga.',
            'Setiap tipe mobil memiliki kelebihan serta kekurangannya masing-masing.'
        ]
    };

    function buildReviews() {
        const reviews = [];
        let id = 1;

        distribution.forEach(([sumber, sentimen, count]) => {
            const examples = sampleText[sentimen];
            for (let index = 0; index < count; index += 1) {
                const teks = examples[index % examples.length];
                reviews.push({
                    id: id++,
                    teks,
                    sumber,
                    tanggal_komentar: '28/07/2026',
                    tanggal: '28/07/2026',
                    hasil: teks.toLowerCase()
                        .replace(/[^a-z0-9\s]/g, '')
                        .replace(/\s+/g, ' ')
                        .trim(),
                    sentimen
                });
            }
        });

        return reviews;
    }

    const reviews = buildReviews();
    const tampilPayload = {
        status: 'success',
        data: reviews,
        statistik_data: {
            total_data_db: 5122,
            total_sudah_preprocessing: 3096,
            platform_db: {
                Youtube: 2437,
                Tiktok: 2389,
                Instagram: 296
            },
            platform_preprocessed: {
                Youtube: 1730,
                Tiktok: 1164,
                Instagram: 202
            },
            log_preprocessing: {
                total_sebelum: 5122,
                total_sesudah: 3096,
                per_platform_sebelum: {
                    Youtube: 2437,
                    Tiktok: 2389,
                    Instagram: 296
                },
                per_platform_sesudah: {
                    Youtube: 1730,
                    Tiktok: 1164,
                    Instagram: 202
                }
            }
        }
    };

    const evaluationPayload = {
        status: 'success',
        akurasi: 82.42,
        total_data: 3096,
        total_training: 2476,
        total_testing: 620,
        cm: {
            pos_pos: 275,
            pos_neg: 3,
            pos_net: 35,
            neg_pos: 6,
            neg_neg: 43,
            neg_net: 22,
            net_pos: 31,
            net_neg: 12,
            net_net: 193
        }
    };

    function jsonResponse(payload) {
        return Promise.resolve(new Response(JSON.stringify(payload), {
            status: 200,
            headers: { 'Content-Type': 'application/json; charset=utf-8' }
        }));
    }

    function analyzeDemoSentence(init) {
        let kalimat = '';
        try {
            kalimat = JSON.parse(init && init.body ? init.body : '{}').kalimat || '';
        } catch (error) {
            kalimat = '';
        }

        const cleaned = kalimat.toLowerCase()
            .replace(/[^a-z0-9\s]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
        const positiveWords = ['bagus', 'nyaman', 'hemat', 'irit', 'suka', 'puas', 'mantap', 'keren'];
        const negativeWords = ['buruk', 'keras', 'boros', 'jelek', 'kecewa', 'kurang', 'lambat', 'mahal'];
        const tokens = cleaned.split(' ').filter(Boolean);
        const positiveHits = tokens.filter(token => positiveWords.includes(token));
        const negativeHits = tokens.filter(token => negativeWords.includes(token));
        const sentimen = positiveHits.length > negativeHits.length
            ? 'POSITIF'
            : negativeHits.length > positiveHits.length
                ? 'NEGATIF'
                : 'NETRAL';

        return {
            status: 'success',
            kalimat_asli: kalimat,
            hasil_preprocessing: cleaned,
            sentimen,
            skor_lexicon: {
                positif: positiveHits.length,
                negatif: negativeHits.length,
                detail_positif: positiveHits,
                detail_negatif: negativeHits
            },
            total_data_training: 2476
        };
    }

    const nativeFetch = window.fetch.bind(window);
    window.fetch = function (input, init) {
        const requestUrl = typeof input === 'string' ? input : input.url;

        if (!requestUrl.includes('/cgi-bin/')) {
            return nativeFetch(input, init);
        }
        if (requestUrl.includes('/cgi-bin/tampil.py')) {
            return jsonResponse(tampilPayload);
        }
        if (requestUrl.includes('/cgi-bin/get_akurasi.py')) {
            return jsonResponse(evaluationPayload);
        }
        if (requestUrl.includes('/cgi-bin/detail_tfidf.py')) {
            return jsonResponse({
                status: 'success',
                teks: 'mobil lcgc nyaman hemat bahan bakar keluarga',
                data: [
                    { term: 'nyaman', tf: 1, tfidf: 0.4381 },
                    { term: 'hemat', tf: 1, tfidf: 0.3917 },
                    { term: 'keluarga', tf: 1, tfidf: 0.3274 },
                    { term: 'bahan bakar', tf: 1, tfidf: 0.2958 }
                ]
            });
        }
        if (requestUrl.includes('/cgi-bin/uji_sentimen.py')) {
            return jsonResponse(analyzeDemoSentence(init));
        }
        if (requestUrl.includes('/cgi-bin/login.py')) {
            return jsonResponse({ status: 'success', id_admin: 1 });
        }

        return jsonResponse({
            status: 'success',
            message: 'Simulasi berhasil dijalankan pada mode demo GitHub Pages.'
        });
    };
}());
