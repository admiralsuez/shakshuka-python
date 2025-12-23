import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

class QRScannerScreen extends StatefulWidget {
  const QRScannerScreen({super.key});

  @override
  State<QRScannerScreen> createState() => _QRScannerScreenState();
}

class _QRScannerScreenState extends State<QRScannerScreen> {
  final MobileScannerController _controller = MobileScannerController();
  final ApiService _api = ApiService();
  final StorageService _storage = StorageService();

  bool _isProcessing = false;
  bool _isPairing = false;
  String? _error;
  String? _scannedUrl;
  final _codeController = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    _codeController.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_isProcessing || _isPairing) return;

    final barcode = capture.barcodes.firstOrNull;
    if (barcode?.rawValue == null) return;

    final value = barcode!.rawValue!;

    // Expected format: shakshuka://pair?url=http://192.168.x.x:8989
    // Or just: http://192.168.x.x:8989
    setState(() {
      _isProcessing = true;
      _error = null;
    });

    String serverUrl;
    if (value.startsWith('shakshuka://pair?url=')) {
      serverUrl = value.substring('shakshuka://pair?url='.length);
    } else if (value.startsWith('http://') || value.startsWith('https://')) {
      serverUrl = value;
    } else {
      setState(() {
        _error = 'Invalid QR code format';
        _isProcessing = false;
      });
      return;
    }

    // Remove trailing slash
    if (serverUrl.endsWith('/')) {
      serverUrl = serverUrl.substring(0, serverUrl.length - 1);
    }

    setState(() {
      _scannedUrl = serverUrl;
      _isProcessing = false;
    });

    _controller.stop();
  }

  Future<void> _pairWithCode() async {
    final code = _codeController.text.trim();
    if (code.isEmpty || code.length != 6) {
      setState(() => _error = 'Please enter the 6-digit code');
      return;
    }

    if (_scannedUrl == null) {
      setState(() => _error = 'No server URL detected');
      return;
    }

    setState(() {
      _isPairing = true;
      _error = null;
    });

    final result = await _api.pairWithServer(
      serverUrl: _scannedUrl!,
      code: code,
      deviceName: 'Android Phone',
    );

    setState(() => _isPairing = false);

    if (result['success'] == true) {
      if (mounted) {
        Navigator.pop(context, true);
      }
    } else {
      setState(() => _error = result['message']);
    }
  }

  void _rescan() {
    setState(() {
      _scannedUrl = null;
      _error = null;
      _codeController.clear();
    });
    _controller.start();
  }

  Future<void> _unpair() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF16213E),
        title: const Text('Unpair Device?'),
        content: const Text(
          'This will disconnect from your PC. You can pair again anytime.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text(
              'Unpair',
              style: TextStyle(color: Colors.red),
            ),
          ),
        ],
      ),
    );

    if (confirm == true) {
      await _storage.unpairDevice();
      if (mounted) {
        Navigator.pop(context, false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final device = _storage.getPairedDevice();

    return Scaffold(
      appBar: AppBar(
        title: Text(device != null ? 'Connection' : 'Pair with PC'),
      ),
      body: device != null
          ? _buildPairedView(device)
          : _scannedUrl != null
              ? _buildCodeEntry()
              : _buildScanner(),
    );
  }

  Widget _buildPairedView(device) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.check_circle,
            size: 80,
            color: Colors.green,
          ),
          const SizedBox(height: 24),
          const Text(
            'Paired with PC',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            device.displayUrl,
            style: TextStyle(
              fontSize: 16,
              color: Colors.grey[400],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Paired on ${device.pairedAt.toString().split('.').first}',
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey[600],
            ),
          ),
          const SizedBox(height: 48),
          OutlinedButton.icon(
            onPressed: _unpair,
            icon: const Icon(Icons.link_off),
            label: const Text('Unpair Device'),
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.red,
              side: const BorderSide(color: Colors.red),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildScanner() {
    return Stack(
      children: [
        MobileScanner(
          controller: _controller,
          onDetect: _onDetect,
        ),
        Container(
          decoration: BoxDecoration(
            color: Colors.black.withOpacity(0.5),
          ),
          child: Center(
            child: Container(
              width: 250,
              height: 250,
              decoration: BoxDecoration(
                border: Border.all(color: const Color(0xFFE85D04), width: 3),
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
        ),
        Positioned(
          bottom: 100,
          left: 0,
          right: 0,
          child: Column(
            children: [
              const Text(
                'Scan QR code from PC Settings',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 16),
                Container(
                  margin: const EdgeInsets.symmetric(horizontal: 32),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.red.withOpacity(0.9),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    _error!,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white),
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildCodeEntry() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.qr_code_scanner,
            size: 64,
            color: Color(0xFFE85D04),
          ),
          const SizedBox(height: 24),
          const Text(
            'QR Code Scanned!',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Server: $_scannedUrl',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[400],
            ),
          ),
          const SizedBox(height: 32),
          const Text(
            'Enter the 6-digit code shown on your PC:',
            style: TextStyle(fontSize: 16),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _codeController,
            keyboardType: TextInputType.number,
            textAlign: TextAlign.center,
            maxLength: 6,
            style: const TextStyle(
              fontSize: 32,
              letterSpacing: 8,
              fontWeight: FontWeight.bold,
            ),
            decoration: InputDecoration(
              counterText: '',
              hintText: '000000',
              filled: true,
              fillColor: const Color(0xFF16213E),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: Color(0xFFE85D04)),
              ),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 16),
            Text(
              _error!,
              style: const TextStyle(color: Colors.red),
            ),
          ],
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _isPairing ? null : _pairWithCode,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFE85D04),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: _isPairing
                  ? const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Text(
                      'Pair',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
            ),
          ),
          const SizedBox(height: 16),
          TextButton(
            onPressed: _rescan,
            child: const Text('Scan Different QR Code'),
          ),
        ],
      ),
    );
  }
}
