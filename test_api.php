<?php

$secret = '0af47e3da21c0ab66516c12198fd99dd1062c28ed1064007e487e8f2a4f4be0a';
$data = [
    'file_name' => 'test_image.png',
    'shop' => 'Test Shop',
    'source_order_id' => '12345',
    'design' => [
        'image_url' => 'https://via.placeholder.com/300x300.png',
        'width' => 10.0,
        'height' => 10.0,
        'quantity' => 2
    ]
];

$signature = hash_hmac('sha256', json_encode($data), $secret);
$data['signature'] = $signature;

$url = 'http://127.0.0.1:8000/api/incomingorder';

$ch = curl_init($url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    'Accept: application/json'
]);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

echo "HTTP Code: $httpCode\n";
echo "Response: $response\n";
