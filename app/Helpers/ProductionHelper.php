<?php

namespace App\Helpers;

use App\Models\DtfImage;
use App\Services\DropboxService;
use App\Helpers\ImageHelper;
use Illuminate\Support\Facades\Log;

class ProductionHelper
{
    /* ===== Config ===== */
    protected const DEFAULT_DROPBOX_PATH = '/DTF_Files/coldesi/';
    protected const LOCAL_JHDR_DIR       = 'uploads/jhdr_files';
    protected const DEFAULT_PRINT_MODE   = '720x1800 Color Shirt - I Series Film M5';

    // Grid/spacing knobs (points)
    protected const X_SPACING_PT = 18;
    protected const Y_SPACING_PT = 18;
    protected const XG_MARGIN_PT = 0;
    protected const YG_MARGIN_PT = 0;

    // Layout assumptions
    protected const SHEET_WIDTH_IN = 21.9;  // usable width in inches
    protected const GAP_IN         = 0.25;  // gap between images in inches

    public static function addToProduction(DtfImage $image, array $opts = [])
    {
        Log::info("ProductionHelper::addToProduction started for Image ID: {$image->id}");
        error_log("ProductionHelper::addToProduction started for Image ID: {$image->id}");

        $dropboxPath = rtrim($opts['dropbox_path'] ?? self::DEFAULT_DROPBOX_PATH, '/') . '/';
        $printMode   = (string)($opts['print_mode'] ?? self::DEFAULT_PRINT_MODE);
        $deleteHdr   = array_key_exists('delete_jhdr', $opts) ? (bool)$opts['delete_jhdr'] : true;
        $uploadImage = array_key_exists('upload_image', $opts) ? (bool)$opts['upload_image'] : true;
        $overwrite   = array_key_exists('overwrite_img', $opts) ? (bool)$opts['overwrite_img'] : true;

        $qty = max(1, (int)($opts['quantity'] ?? $image->quantity));

        $layout = self::calculate_sheet_layout($image, $qty);

        $baseName      = self::safeBasename((string)$image->image);
        $remoteMainImg = (string)$image->id . '-'  . $baseName;
        $remoteRemImg  = (string)$image->id . 'R-' . $baseName;

        $dropbox = new DropboxService();

        // FULL
        $fullCopies = max(0, $qty - $layout['remaining']);
        if ($fullCopies > 0) {
            $jhdrMainBase = pathinfo($remoteMainImg, PATHINFO_FILENAME);
            $jhdrMainPath = self::create_jhdr_grid_file(
                $jhdrMainBase,
                self::LOCAL_JHDR_DIR,
                $printMode,
                ($opts['rotate'] ?? $layout['rotated']),
                (float)$image->width,
                (float)$image->height,
                $fullCopies,
                $layout['Columns'],
                $layout['Rows'],
                $deleteHdr
            );

            $dropbox->upload($jhdrMainPath, $dropboxPath . $jhdrMainBase . '.jhdr');
            @unlink($jhdrMainPath);

            if ($uploadImage) {
                $localPath = public_path((string)$image->image);
                if (file_exists($localPath)) {
                    // Prepare image for production (resize, 300 DPI, hard edges)
                    $tempImagePath = storage_path('app/temp_' . uniqid() . '.png');
                    $prepareResult = ImageHelper::prepareForProduction(
                        $localPath,
                        $tempImagePath,
                        (float)$image->width,
                        (float)$image->height,
                        300
                    );

                    if ($prepareResult['success']) {
                        $dropbox->upload($tempImagePath, $dropboxPath . $remoteMainImg);
                        @unlink($tempImagePath);
                    } else {
                        Log::error("Failed to prepare image for production: " . ($prepareResult['message'] ?? 'Unknown error'));
                        // Fallback to original if processing fails?
                        // The user said "edit the image to match...", so failing might be better,
                        // but for robustness we might want to upload original or throw error.
                        // Let's throw an exception to be safe and notify the user.
                        throw new \Exception("Failed to process image: " . ($prepareResult['message'] ?? 'Unknown error'));
                    }
                } else {
                    Log::warning("Local image not found for upload: $localPath");
                }
            }
        }

        // REMAINDER
        if ($layout['remaining'] > 0) {
            $remQty = (int)$layout['remaining'];
            $rem    = self::calculate_sheet_layout($image, $remQty);

            $jhdrRemBase = pathinfo($remoteRemImg, PATHINFO_FILENAME);
            $jhdrRemPath = self::create_jhdr_grid_file(
                $jhdrRemBase,
                self::LOCAL_JHDR_DIR,
                $printMode,
                ($opts['rotate'] ?? $rem['rotated']),
                (float)$image->width,
                (float)$image->height,
                $remQty,
                $rem['Columns'],
                $rem['Rows'],
                $deleteHdr
            );

            $dropbox->upload($jhdrRemPath, $dropboxPath . $jhdrRemBase . '.jhdr');
            @unlink($jhdrRemPath);

            if ($uploadImage) {
                $localPath = public_path((string)$image->image);
                if (file_exists($localPath)) {
                    // Prepare image for production (resize, 300 DPI, hard edges)
                    $tempImagePath = storage_path('app/temp_' . uniqid() . '.png');
                    $prepareResult = ImageHelper::prepareForProduction(
                        $localPath,
                        $tempImagePath,
                        (float)$image->width,
                        (float)$image->height,
                        300
                    );

                    if ($prepareResult['success']) {
                        $dropbox->upload($tempImagePath, $dropboxPath . $remoteRemImg);
                        @unlink($tempImagePath);
                    } else {
                        Log::error("Failed to prepare image for production (remainder): " . ($prepareResult['message'] ?? 'Unknown error'));
                        throw new \Exception("Failed to process image (remainder): " . ($prepareResult['message'] ?? 'Unknown error'));
                    }
                } else {
                    Log::warning("Local image not found for upload (remainder): $localPath");
                }
            }
        }

        if (($opts['mark_production'] ?? true) !== false) {
            $image->production = 1;
            $image->save();
        }
    }

    protected static function create_jhdr_grid_file(
        string $filename,
        string $directory,
        string $printMode,
        int $rotateDeg,
        float $width_in,
        float $height_in,
        int $copies,
        int $columns,
        int $rows,
        bool $deleteHdr = true
    ): string {
        $absDir = public_path($directory);
        self::ensureDir($absDir);
        $finalPath = $absDir . DIRECTORY_SEPARATOR . $filename . '.jhdr';
        $tmpPath   = $finalPath . '.tmp';

        // ---- FINAL FIT/CORRECTION ----
        $sheetW = self::SHEET_WIDTH_IN;
        $gap    = self::GAP_IN;

        $effW = ($rotateDeg % 180 === 90) ? $height_in : $width_in;

        $maxCols = max(1, (int)floor( ($sheetW + $gap) / max(0.0001, ($effW + $gap)) ));
        $fitsFn  = static function(int $c, float $w, float $sheet, float $g): bool {
            if ($c <= 0) return false;
            $used = $c * $w + max(0, $c - 1) * $g;
            return $used <= $sheet + 1e-9;
        };
        while ($maxCols > 1 && !$fitsFn($maxCols, $effW, $sheetW, $gap)) $maxCols--;

        if ($columns > $maxCols) {
            $flipW     = ($rotateDeg % 180 === 90) ? $width_in : $height_in;
            $flipMax   = max(1, (int)floor( ($sheetW + $gap) / max(0.0001, ($flipW + $gap)) ));
            while ($flipMax > 1 && !$fitsFn($flipMax, $flipW, $sheetW, $gap)) $flipMax--;

            if ($flipMax >= $columns) {
                $rotateDeg = ($rotateDeg % 180 === 90) ? 0 : 90;
                $effW      = $flipW;
                $maxCols   = $flipMax;
            } else {
                $columns = $maxCols;
                $rows    = max(1, (int)ceil($copies / max(1, $columns)));
            }
        }

        while ($columns > 1 && !$fitsFn($columns, $effW, $sheetW, $gap)) {
            $columns--;
            $rows = max(1, (int)ceil($copies / max(1, $columns)));
        }

        if ($rows === 1 && $columns > $copies) {
            $columns = $copies;
        }

        $wpt = self::toPt($width_in);
        $hpt = self::toPt($height_in);

        // NOTE: The ColDesi/I-Series printer uses SizeType="1" (ratio-based).
        // Since we resize images to the exact target size during preparation,
        // we use a 1:1 ratio (width=1, height=1) in the JHDR file to ensure
        // the printer outputs the file at its native dimensions.
        $xml  = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>' . "\n";
        $xml .= "<JHDR>\n";
        $xml .= "  <DeleteJHDRfile type=\"bool\">" . ($deleteHdr ? '1' : '0') . "</DeleteJHDRfile>\n";
        $xml .= "  <PrintMode name=\"" . self::xmlEscape($printMode) . "\"/>\n";
        $xml .= "  <Size SizeType=\"1\" width=\"1.000000\" height=\"1.000000\"/>\n";
        $xml .= "  <Rotate type=\"int\">" . (int)$rotateDeg . "</Rotate>\n";
        $xml .= "  <CopyGroupInfo>\n";
        $xml .= "    <Version>5</Version>\n";
        $xml .= "    <Copies>" . (int)$copies . "</Copies>\n";
        $xml .= "    <Columns>" . max(1, (int)$columns) . "</Columns>\n";
        $xml .= "    <Rows>"    . max(1, (int)$rows)    . "</Rows>\n";
        $xml .= "    <XSpacing>" . (int)self::X_SPACING_PT . "</XSpacing>\n";
        $xml .= "    <YSpacing>" . (int)self::Y_SPACING_PT . "</YSpacing>\n";
        $xml .= "    <XGMargin>" . (int)self::XG_MARGIN_PT . "</XGMargin>\n";
        $xml .= "    <YGMargin>" . (int)self::YG_MARGIN_PT . "</YGMargin>\n";
        $xml .= "    <DoAreaFill>false</DoAreaFill>\n";
        $xml .= "    <FillWidth>72</FillWidth>\n";
        $xml .= "    <FillLength>72</FillLength>\n";
        $xml .= "    <WidthPercentShift>0</WidthPercentShift>\n";
        $xml .= "    <LengthPercentShift>0</LengthPercentShift>\n";
        $xml .= "    <NumeratorWidth>1</NumeratorWidth>\n";
        $xml .= "    <DenominatorWidth>3</DenominatorWidth>\n";
        $xml .= "    <NumeratorLength>1</NumeratorLength>\n";
        $xml .= "    <DenominatorLength>3</DenominatorLength>\n";
        $xml .= "    <Style>0</Style>\n";
        $xml .= "  </CopyGroupInfo>\n";
        $xml .= "</JHDR>";

        if (file_put_contents($tmpPath, $xml) === false) {
            throw new \RuntimeException('Failed to write JHDR temp file: ' . $tmpPath);
        }
        if (!@rename($tmpPath, $finalPath)) {
            @unlink($tmpPath);
            throw new \RuntimeException('Failed to finalize JHDR file: ' . $finalPath);
        }

        return $finalPath;
    }

    public static function calculate_sheet_layout(DtfImage $image, int $quantity = 0): array
    {
        $w_in = (float)($image->width  ?? 0);
        $h_in = (float)($image->height ?? 0);
        if ($w_in <= 0 || $h_in <= 0) {
            throw new \InvalidArgumentException('Image width/height (inches) must be > 0');
        }

        $quantity = $quantity > 0 ? (int)$quantity : (int)($image->quantity ?? 1);
        if ($quantity <= 0) $quantity = 1;

        $sheetW = self::SHEET_WIDTH_IN;
        $gap    = self::GAP_IN;

        $cols_fit = static function (float $imgW) use ($sheetW, $gap): int {
            $den = $imgW + $gap;
            if ($den <= 0.0001) return 1;
            $c = (int)floor(($sheetW + $gap) / $den);
            return max(1, $c);
        };
        $fits = static function (int $c, float $imgW, float $sheetW, float $gap): bool {
            if ($c <= 0) return false;
            $used = $c * $imgW + max(0, $c - 1) * $gap;
            return $used <= $sheetW + 1e-9;
        };

        $cols_no_rot = max(1, $cols_fit($w_in));
        while ($cols_no_rot > 1 && !$fits($cols_no_rot, $w_in, $sheetW, $gap)) $cols_no_rot--;

        $cols_rot = max(1, $cols_fit($h_in));
        while ($cols_rot > 1 && !$fits($cols_rot, $h_in, $sheetW, $gap)) $cols_rot--;

        $rotated = 0;
        $cols    = $cols_no_rot;

        if ($cols_rot > $cols_no_rot) {
            $rotated = 90;
            $cols    = $cols_rot;
        } elseif ($cols_rot === $cols_no_rot) {
            $rows_no_rot_total = (int)ceil($quantity / max(1, $cols_no_rot));
            $rows_rot_total    = (int)ceil($quantity / max(1, $cols_rot));
            if ($rows_rot_total < $rows_no_rot_total) {
                $rotated = 90;
                $cols    = $cols_rot;
            }
        }

        if ($quantity < $cols) {
            $cols = $quantity;
        }

        $rows_total = (int)ceil($quantity / max(1, $cols));
        $remainder  = $quantity % max(1, $cols);

        $rows_full  = $rows_total;
        $remaining  = 0;
        if ($remainder > 0 && $quantity > $cols) {
            $rows_full = max(1, $rows_total - 1);
            $remaining = $remainder;
        }

        return [
            'Columns'   => (int)$cols,
            'Rows'      => (int)$rows_full,
            'rotated'   => (int)$rotated,
            'remaining' => (int)$remaining,
        ];
    }

    protected static function toPt($inches): string
    {
        return number_format(((float)$inches) * 72, 2, '.', '');
    }

    protected static function safeBasename(string $path): string
    {
        $base = basename(parse_url($path, PHP_URL_PATH) ?: '');
        return $base !== '' ? $base : 'file';
    }

    protected static function ensureDir(string $absDir): void
    {
        if (is_dir($absDir)) return;
        if (!@mkdir($absDir, 0775, true) && !is_dir($absDir)) {
            throw new \RuntimeException('Failed to create directory: ' . $absDir);
        }
    }

    protected static function xmlEscape(string $s): string
    {
        return htmlspecialchars($s, ENT_QUOTES | ENT_XML1, 'UTF-8');
    }
}
