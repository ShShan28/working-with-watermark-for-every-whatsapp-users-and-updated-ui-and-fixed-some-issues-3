<?php
header('Content-Type: application/json');
error_reporting(E_ALL);
ini_set('display_errors', 0);

if(!is_dir('logs')) mkdir('logs', 0777, true);

// UltraMsg config
$instance_id = 'instance153584';
$token = 'vman605et11n5ov8';

$input = json_decode(file_get_contents('php://input'), true);
if (!$input) { echo json_encode(['error'=>'No input received']); exit; }

$to = trim($input['to'] ?? '');
$body = trim($input['body'] ?? '');
$base64 = trim($input['base64'] ?? '');
$filename = trim($input['filename'] ?? '');

if (!$to) { echo json_encode(['error'=>[['to'=>'is required']]]); exit; }
if (!$body && !$base64) $body = ' '; // UltraMsg needs something

// Determine endpoint
if ($base64 && $filename){
    $url = "https://api.ultramsg.com/$instance_id/messages/document?token=$token";
    $post_data = [
        'to' => $to,
        'document' => $base64,
        'filename' => $filename,
        'caption' => $body
    ];
} else {
    $url = "https://api.ultramsg.com/$instance_id/messages/chat?token=$token";
    $post_data = [
        'to' => $to,
        'body' => $body
    ];
}

// cURL
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $url);
curl_setopt($ch, CURLOPT_POST, 1);
curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($post_data));
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = curl_exec($ch);
$err = curl_error($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

// Save server log
$log_entry = [
    'time' => date('Y-m-d H:i:s'),
    'to' => $to,
    'filename' => $filename,
    'message' => $body,
    'http' => $http_code,
    'response' => $response
];
file_put_contents('logs/server_logs.json', json_encode($log_entry, JSON_UNESCAPED_UNICODE).PHP_EOL, FILE_APPEND);

// Return response
if($err) echo json_encode(['error'=>$err]);
else echo $response;