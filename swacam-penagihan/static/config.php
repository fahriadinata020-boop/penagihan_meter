<?php
// Alamat backend (FastAPI) aplikasi ini.
$envApiBase = getenv('API_BASE_URL');
if ($envApiBase !== false && trim($envApiBase) !== '') {
    define('API_BASE_URL', rtrim(trim($envApiBase), '/'));
} else {
    define('API_BASE_URL', 'http://localhost:8001');
}

// Alamat HALAMAN WEB aplikasi Catat Meter (dipakai tombol "pindah aplikasi" di sidebar).
// Contoh lokal: php -S localhost:8080 -t <folder aplikasi lain>/static
$envPeer = getenv('PEER_APP_URL');
if ($envPeer !== false && trim($envPeer) !== '') {
    define('PEER_APP_URL', rtrim(trim($envPeer), '/'));
} else {
    define('PEER_APP_URL', 'http://localhost:8080');
}
