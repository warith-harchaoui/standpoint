<?php
// serve.php — the only path to the app's files. The bundle .htaccess rewrites
// every protected URL (index.html, backend-pyodide.js, py/, wheels/, i18n/,
// vocab/, examples/, llm-engine/) here, so Apache never serves them directly:
// no cookie, no file — guessing an asset URL yields the same 403 as the front
// door.
//
// llm-engine/ is the distilled model the Laziness button downloads, and its
// onnx/ payload is ~620 MB. That one file is why this script streams in chunks
// and honours Range requests: readfile() on shared hosting would meet
// memory_limit, and without Range a dropped connection restarts the whole
// download from zero.

declare(strict_types=1);

require __DIR__ . '/auth.php';

// The protected tail of the URL, matched with a charset too narrow to smuggle
// query strings or encodings in; realpath below re-checks against traversal.
$path = (string) parse_url($_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH);
$ok = preg_match(
    '#/(index\.html|backend-pyodide\.js'
        . '|(?:py|wheels|i18n|vocab|examples)/[A-Za-z0-9._-]+'
        // llm-engine/ is the one folder with a subdirectory of its own
        // (onnx/), so it gets its own alternative rather than a looser
        // catch-all that would widen every other prefix too.
        . '|llm-engine/(?:onnx/)?[A-Za-z0-9._-]+'
        . ')$#',
    $path,
    $m
);
if (!$ok) {
    http_response_code(404);
    exit;
}
$rel = $m[1];

$email = current_email();
if ($email === null) {
    if ($rel === 'index.html') {
        // A person following an old bookmark: send them to the landing form.
        header('Location: ' . gate_base_url() . '/?login=required');
    } else {
        http_response_code(403);
    }
    exit;
}

$root = realpath(gate_root());
$file = realpath(gate_root() . '/' . $rel);
if ($file === false || $root === false || !str_starts_with($file, $root . DIRECTORY_SEPARATOR)) {
    http_response_code(404);
    exit;
}

// Entering the app page is the session-level activity signal; individual
// assets would only repeat it (the in-page beacon covers the fine grain).
if ($rel === 'index.html') {
    log_event($email, 'app_page');
}

$types = [
    'html' => 'text/html; charset=UTF-8',
    'js' => 'application/javascript; charset=UTF-8',
    'json' => 'application/json; charset=UTF-8',
    'py' => 'text/x-python; charset=UTF-8',
    'csv' => 'text/csv; charset=UTF-8',
    'txt' => 'text/plain; charset=UTF-8',
    'whl' => 'application/octet-stream',
    'onnx' => 'application/octet-stream',
];
$ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
$size = (int) filesize($file);

// Range support, for the ~620 MB model: a browser that loses the connection
// resumes instead of starting over, and onnxruntime-web is free to ask for the
// tail of the file first if it wants the metadata before the weights.
$start = 0;
$end = $size - 1;
$partial = false;
$range = $_SERVER['HTTP_RANGE'] ?? '';
if ($range !== '' && preg_match('/^bytes=(\d*)-(\d*)$/', $range, $r)) {
    $reqStart = $r[1] === '' ? null : (int) $r[1];
    $reqEnd = $r[2] === '' ? null : (int) $r[2];
    if ($reqStart === null && $reqEnd !== null) {
        $start = max(0, $size - $reqEnd);          // suffix range: last N bytes
    } elseif ($reqStart !== null) {
        $start = $reqStart;
        if ($reqEnd !== null) {
            $end = min($reqEnd, $size - 1);
        }
    }
    if ($start > $end || $start >= $size) {
        http_response_code(416);
        header('Content-Range: bytes */' . $size);
        exit;
    }
    $partial = true;
}

header('Content-Type: ' . ($types[$ext] ?? 'application/octet-stream'));
header('Accept-Ranges: bytes');
// Private: cacheable by the authenticated browser (the model is hundreds of MB),
// never by shared caches that would bypass the gate.
header('Cache-Control: private, max-age=86400');
if ($partial) {
    http_response_code(206);
    header('Content-Range: bytes ' . $start . '-' . $end . '/' . $size);
}
header('Content-Length: ' . (string) ($end - $start + 1));

// Stream in chunks rather than readfile(): the model does not fit in a shared
// host's memory_limit, and output buffering would try to hold all of it.
while (ob_get_level() > 0) {
    ob_end_flush();
}
set_time_limit(0);
$fh = fopen($file, 'rb');
if ($fh === false) {
    http_response_code(500);
    exit;
}
fseek($fh, $start);
$remaining = $end - $start + 1;
while ($remaining > 0 && !feof($fh) && !connection_aborted()) {
    $chunk = fread($fh, (int) min(1 << 20, $remaining));
    if ($chunk === false || $chunk === '') {
        break;
    }
    echo $chunk;
    flush();
    $remaining -= strlen($chunk);
}
fclose($fh);
