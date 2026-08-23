<?php

namespace Tests\Feature\Mail;

use App\Mail\AdminNewOrderPlaced;
use App\Mail\OrderDelivered;
use App\Mail\OrderInProduction;
use App\Mail\OrderOutForDelivery;
use App\Mail\OrderPlaced;
use App\Mail\OrderReadyForPickup;
use App\Mail\OrderShipped;
use App\Models\Business;
use App\Models\DtfOrder;
use Illuminate\Mail\Mailable;
use Illuminate\Mail\MailManager;
use Illuminate\Mail\Transport\ArrayTransport;
use PHPUnit\Framework\Attributes\DataProvider;
use Symfony\Component\Mime\Email;
use Tests\TestCase;

class OrderStatusMailRenderingTest extends TestCase
{
    /**
     * @return array<string, array{class-string<Mailable>, string, list<string>}>
     */
    public static function productionMarkdownMailables(): array
    {
        return [
            'admin new order' => [
                AdminNewOrderPlaced::class,
                'New order placed #4242',
                [
                    'New Order Placed',
                    'Business: River & Dye <Studio>',
                    'Customer Email: orders+render@example.test',
                    'Total: $123.45',
                    'View Order',
                ],
            ],
            'customer order received' => [
                OrderPlaced::class,
                'Order #4242 received',
                [
                    'Order Received',
                    'Order #4242',
                    'Order total: $123.45',
                    'Date: Aug 23, 2026',
                    'Buy DTF Render Test',
                ],
            ],
            'order in production' => [
                OrderInProduction::class,
                'Order #4242 is in production',
                [
                    'Order In Production',
                    'Order #4242',
                    'ready for pickup or shipped',
                    'Buy DTF Render Test',
                ],
            ],
            'order shipped' => [
                OrderShipped::class,
                'Your Order #4242 has shipped!',
                [
                    'Your Order has Shipped!',
                    'Hello River & Dye <Studio>',
                    'order #4242',
                    'Tracking Number: 1Z999AA10123456784',
                    'Track Your Package',
                ],
            ],
            'order out for delivery' => [
                OrderOutForDelivery::class,
                'Your Order #4242 is out for delivery!',
                [
                    'Your Order is Out for Delivery!',
                    'Hello River & Dye <Studio>',
                    'order #4242',
                    'Tracking Number: 1Z999AA10123456784',
                    'Track Your Package',
                ],
            ],
            'order ready for pickup' => [
                OrderReadyForPickup::class,
                'Your Order #4242 is ready for pickup!',
                [
                    'Your Order is Ready for Pickup!',
                    'Hello River & Dye <Studio>',
                    'order #4242',
                    '123 Render Way',
                    'Testville, IN 46350',
                ],
            ],
            'order delivered' => [
                OrderDelivered::class,
                'Your Order #4242 has been delivered!',
                [
                    'Your Order has been Delivered!',
                    'Hello River & Dye <Studio>',
                    'order #4242',
                    'Tracking Number: 1Z999AA10123456784',
                    'View Tracking Details',
                ],
            ],
        ];
    }

    /**
     * @param  class-string<Mailable>  $mailableClass
     * @param  list<string>  $bodyFragments
     */
    #[DataProvider('productionMarkdownMailables')]
    public function test_production_markdown_mail_renders_as_a_valid_mime_message_without_outbound_io(
        string $mailableClass,
        string $expectedSubject,
        array $bodyFragments,
    ): void {
        config([
            'app.name' => 'Buy DTF Render Test',
            'mail.default' => 'array',
            'mail.from.address' => 'no-reply@example.test',
            'mail.from.name' => 'Buy DTF Render Test & QA',
            'services.shippo.from_address.street1' => '123 Render Way',
            'services.shippo.from_address.city' => 'Testville',
            'services.shippo.from_address.state' => 'IN',
            'services.shippo.from_address.zip' => '46350',
        ]);

        $mailManager = $this->app->make(MailManager::class);
        $mailManager->forgetMailers();
        $mailer = $mailManager->mailer('array');
        $transport = $mailer->getSymfonyTransport();

        $this->assertInstanceOf(ArrayTransport::class, $transport);
        $transport->flush();

        $mailable = new $mailableClass($this->orderFixture());
        $sent = $mailable
            ->to('render-recipient@example.test', 'Render Recipient')
            ->send($mailer);

        $this->assertNotNull($sent);
        $this->assertCount(1, $transport->messages());

        $symfonySentMessage = $sent->getSymfonySentMessage();
        $message = $symfonySentMessage->getOriginalMessage();

        $this->assertInstanceOf(Email::class, $message);
        $this->assertSame($expectedSubject, $message->getSubject());
        $this->assertDoesNotMatchRegularExpression('/[\r\n]/', $message->getSubject());
        $this->assertSame('render-recipient@example.test', $message->getTo()[0]->getAddress());
        $this->assertSame('no-reply@example.test', $message->getFrom()[0]->getAddress());
        $this->assertSame('Buy DTF Render Test & QA', $message->getFrom()[0]->getName());
        $this->assertSame([], $message->getAttachments());

        $htmlBody = $message->getHtmlBody();
        $textBody = $message->getTextBody();

        $this->assertIsString($htmlBody);
        $this->assertIsString($textBody);
        $this->assertNotSame('', trim($htmlBody));
        $this->assertNotSame('', trim($textBody));

        $normalizedHtml = $this->normalizeBody(html_entity_decode(
            strip_tags($htmlBody),
            ENT_QUOTES | ENT_HTML5,
            'UTF-8',
        ));
        $normalizedText = $this->normalizeBody($textBody);

        foreach ($bodyFragments as $fragment) {
            $this->assertStringContainsString($fragment, $normalizedHtml);
            $this->assertStringContainsString($fragment, $normalizedText);
        }

        $this->assertStringNotContainsString('{{', $htmlBody);
        $this->assertStringNotContainsString('<x-mail::', $htmlBody);

        $mime = $symfonySentMessage->toString();

        $this->assertStringContainsString('Subject: '.$expectedSubject."\r\n", $mime);
        $this->assertStringContainsString('Content-Type: multipart/alternative;', $mime);
        $this->assertStringContainsString('Content-Type: text/plain; charset=utf-8', $mime);
        $this->assertStringContainsString('Content-Type: text/html; charset=utf-8', $mime);
    }

    private function orderFixture(): DtfOrder
    {
        $business = new Business;
        $business->forceFill([
            'id' => 101,
            'business_name' => 'River & Dye <Studio>',
            'contact_name' => 'River & Dye <Studio>',
            'email' => 'orders+render@example.test',
        ]);

        $order = new DtfOrder;
        $order->forceFill([
            'id' => 4242,
            'business_id' => 101,
            'order_date' => '2026-08-23',
            'total_price' => 123.45,
            'tracking_number' => '1Z999AA10123456784',
        ]);
        $order->setRelation('business', $business);

        return $order;
    }

    private function normalizeBody(string $body): string
    {
        $body = str_replace(['**', '__'], '', $body);

        return trim((string) preg_replace('/\s+/', ' ', $body));
    }
}
