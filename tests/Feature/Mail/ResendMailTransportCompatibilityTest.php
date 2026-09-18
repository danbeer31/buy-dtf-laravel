<?php

namespace Tests\Feature\Mail;

use App\Mail\OrderPlaced;
use App\Models\Business;
use App\Models\DtfOrder;
use Illuminate\Mail\MailManager;
use Illuminate\Mail\Transport\ResendTransport;
use Resend\Client as ResendClient;
use Resend\Contracts\Transporter;
use Resend\ValueObjects\Transporter\BaseUri;
use Resend\ValueObjects\Transporter\Headers;
use Resend\ValueObjects\Transporter\Payload;
use Symfony\Component\Mime\Email;
use Tests\TestCase;

class ResendMailTransportCompatibilityTest extends TestCase
{
    public function test_rendered_order_mail_is_handed_to_resend_without_credentials_or_network_io(): void
    {
        config([
            'app.name' => 'Buy DTF Resend Test',
            'mail.default' => 'resend',
            'mail.from.address' => 'no-reply@example.test',
            'mail.from.name' => 'Buy DTF Resend Test',
            'mail.mailers.resend' => [
                'transport' => 'resend',
                'key' => 'test-only-key-never-sent',
            ],
        ]);

        $capturingTransporter = new class implements Transporter
        {
            /** @var list<Payload> */
            public array $payloads = [];

            public function request(Payload $payload): array
            {
                $this->payloads[] = $payload;

                return ['id' => 'resend-message-step2-test'];
            }
        };

        $mailManager = $this->app->make(MailManager::class);
        $mailManager->forgetMailers();
        $mailManager->extend(
            'resend',
            static fn (array $config): ResendTransport => new ResendTransport(
                new ResendClient($capturingTransporter)
            )
        );

        $mailer = $mailManager->mailer('resend');
        $transport = $mailer->getSymfonyTransport();

        $this->assertInstanceOf(ResendTransport::class, $transport);

        $sent = (new OrderPlaced($this->orderFixture()))
            ->to('resend-recipient@example.test', 'Resend Recipient')
            ->send($mailer);

        $this->assertNotNull($sent);
        $this->assertCount(1, $capturingTransporter->payloads);

        $message = $sent->getSymfonySentMessage()->getOriginalMessage();

        $this->assertInstanceOf(Email::class, $message);
        $this->assertSame(
            'resend-message-step2-test',
            $message->getHeaders()->get('X-Resend-Email-ID')?->getBodyAsString()
        );

        $request = $capturingTransporter->payloads[0]->toRequest(
            BaseUri::from('resend.example.test'),
            new Headers([])
        );
        $payload = json_decode((string) $request->getBody(), true, flags: JSON_THROW_ON_ERROR);

        $this->assertSame('POST', $request->getMethod());
        $this->assertSame('https://resend.example.test/emails', (string) $request->getUri());
        $this->assertSame('application/json', $request->getHeaderLine('Content-Type'));
        $this->assertStringStartsWith('resend-php/', $request->getHeaderLine('User-Agent'));
        $this->assertFalse($request->hasHeader('Authorization'));

        $this->assertStringContainsString('no-reply@example.test', $payload['from']);
        $this->assertSame(['"Resend Recipient" <resend-recipient@example.test>'], $payload['to']);
        $this->assertSame('Order #4242 received', $payload['subject']);
        $this->assertStringContainsString('Order Received', $payload['html']);
        $this->assertStringContainsString('Order Received', $payload['text']);
        $this->assertSame([], $payload['attachments']);
    }

    private function orderFixture(): DtfOrder
    {
        $business = new Business;
        $business->forceFill([
            'id' => 101,
            'business_name' => 'Resend Test Business',
            'contact_name' => 'Resend Test Customer',
            'email' => 'customer@example.test',
        ]);

        $order = new DtfOrder;
        $order->forceFill([
            'id' => 4242,
            'business_id' => 101,
            'order_date' => '2026-08-23',
            'total_price' => 123.45,
        ]);
        $order->setRelation('business', $business);

        return $order;
    }
}
