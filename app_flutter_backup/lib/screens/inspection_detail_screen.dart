import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/index.dart';
import '../providers/index.dart';
import '../services/index.dart';

/// 巡查详情屏幕（拍照和上报）
class InspectionDetailScreen extends ConsumerStatefulWidget {
  final HeritageSite heritage;

  const InspectionDetailScreen({
    Key? key,
    required this.heritage,
  }) : super(key: key);

  @override
  ConsumerState<InspectionDetailScreen> createState() =>
      _InspectionDetailScreenState();
}

class _InspectionDetailScreenState
    extends ConsumerState<InspectionDetailScreen> {
  late CameraService _cameraService;
  late LocationService _locationService;

  String? _selectedPhotoPath;
  bool _isNormal = true;
  final _issueController = TextEditingController();
  bool _isSubmitting = false;
  double? _currentLat;
  double? _currentLon;

  @override
  void initState() {
    super.initState();
    _cameraService = CameraService();
    _locationService = LocationService();
    _getCurrentLocation();
  }

  @override
  void dispose() {
    _issueController.dispose();
    super.dispose();
  }

  Future<void> _getCurrentLocation() async {
    try {
      final position = await _locationService.getCurrentLocation();
      if (position != null) {
        setState(() {
          _currentLat = position.latitude;
          _currentLon = position.longitude;
        });
      }
    } catch (e) {
      print('获取位置失败: $e');
    }
  }

  Future<void> _takePhoto() async {
    try {
      final image = await _cameraService.takePhoto();
      if (image != null) {
        final savedPath = await _cameraService.saveImageLocally(image.path);
        if (savedPath != null && mounted) {
          setState(() => _selectedPhotoPath = savedPath);
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('照片已拍摄')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('拍照失败: $e')),
        );
      }
    }
  }

  Future<void> _pickPhotoFromGallery() async {
    try {
      final image = await _cameraService.pickPhotoFromGallery();
      if (image != null) {
        final savedPath = await _cameraService.saveImageLocally(image.path);
        if (savedPath != null && mounted) {
          setState(() => _selectedPhotoPath = savedPath);
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('选择图片失败: $e')),
        );
      }
    }
  }

  Future<void> _submitInspection() async {
    if (_selectedPhotoPath == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先拍摄或选择照片')),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    try {
      // 为图片添加水印（经纬度、时间、文物点名称）
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('正在处理图片水印...')),
      );

      String photoPathToSubmit = _selectedPhotoPath!;
      
      // 调用水印添加功能
      final watermarkedPath = await _cameraService.addWatermark(
        imagePath: _selectedPhotoPath!,
        latitude: _currentLat,
        longitude: _currentLon,
        siteName: widget.heritage.name,
        inspectorName: null, // 可从用户信息中获取
      );

      // 如果水印添加成功，使用带水印的图片；否则使用原图
      if (watermarkedPath != null) {
        photoPathToSubmit = watermarkedPath;
        print('已使用带水印的图片: $watermarkedPath');
      } else {
        print('水印添加失败，将使用原图上传');
      }

      final inspectionsNotifier =
          ref.read(myInspectionsProvider.notifier);
      
      final success = await inspectionsNotifier.createInspection(
        siteId: widget.heritage.id,
        siteName: widget.heritage.name,
        isNormal: _isNormal,
        issueDetails: _issueController.text.trim(),
        photoPath: photoPathToSubmit,
        latitude: _currentLat,
        longitude: _currentLon,
      );

      if (success && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('巡查记录已保存（含水印）')),
        );
        Navigator.of(context).pop();
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('保存失败，请重试')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('提交失败: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isSubmitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('巡查记录'),
        elevation: 2,
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 文物点信息卡片
            Card(
              margin: const EdgeInsets.all(16),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.heritage.name,
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Icon(Icons.location_on, size: 16, color: Colors.grey),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(widget.heritage.address),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(Icons.inventory_2, size: 16, color: Colors.grey),
                        const SizedBox(width: 8),
                        Text(widget.heritage.getCategoryName()),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(Icons.shield, size: 16, color: Colors.grey),
                        const SizedBox(width: 8),
                        Text(widget.heritage.getLevelName()),
                      ],
                    ),
                  ],
                ),
              ),
            ),

            // 拍照区域
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '现场照片',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (_selectedPhotoPath != null)
                    Stack(
                      children: [
                        Container(
                          width: double.infinity,
                          height: 300,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(8),
                            image: DecorationImage(
                              image: FileImage(File(_selectedPhotoPath!)),
                              fit: BoxFit.cover,
                            ),
                          ),
                        ),
                        Positioned(
                          top: 8,
                          right: 8,
                          child: FloatingActionButton(
                            mini: true,
                            backgroundColor: Colors.red,
                            onPressed: () {
                              setState(() => _selectedPhotoPath = null);
                            },
                            child: const Icon(Icons.close),
                          ),
                        ),
                      ],
                    )
                  else
                    Container(
                      width: double.infinity,
                      height: 300,
                      decoration: BoxDecoration(
                        color: Colors.grey[100],
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: Colors.grey[300]!,
                          width: 2,
                        ),
                      ),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.camera_alt,
                            size: 48,
                            color: Colors.grey[400],
                          ),
                          const SizedBox(height: 16),
                          Text(
                            '请拍摄文物现场照片',
                            style: TextStyle(
                              fontSize: 14,
                              color: Colors.grey[600],
                            ),
                          ),
                        ],
                      ),
                    ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: _takePhoto,
                          icon: const Icon(Icons.camera_alt),
                          label: const Text('拍照'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: _pickPhotoFromGallery,
                          icon: const Icon(Icons.image),
                          label: const Text('从相册选择'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),

            const SizedBox(height: 24),

            // 检查状态
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '检查状态',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: ChoiceChip(
                          label: const Text('正常'),
                          selected: _isNormal,
                          onSelected: (selected) {
                            setState(() => _isNormal = true);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: ChoiceChip(
                          label: const Text('异常'),
                          selected: !_isNormal,
                          onSelected: (selected) {
                            setState(() => _isNormal = false);
                          },
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),

            const SizedBox(height: 24),

            // 问题描述
            if (!_isNormal)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '问题描述',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _issueController,
                      maxLines: 3,
                      decoration: InputDecoration(
                        hintText: '请描述发现的问题...',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                  ],
                ),
              ),

            // 位置信息
            if (_currentLat != null && _currentLon != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.location_on, size: 16, color: Colors.green),
                            const SizedBox(width: 8),
                            const Text(
                              '已记录位置信息',
                              style: TextStyle(fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          '纬度: $_currentLat',
                          style: const TextStyle(fontSize: 12),
                        ),
                        Text(
                          '经度: $_currentLon',
                          style: const TextStyle(fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

            const SizedBox(height: 24),

            // 提交按钮
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
              child: SizedBox(
                width: double.infinity,
                height: 50,
                child: ElevatedButton.icon(
                  onPressed: _isSubmitting ? null : _submitInspection,
                  icon: _isSubmitting
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor:
                                AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        )
                      : const Icon(Icons.upload),
                  label: Text(
                    _isSubmitting ? '提交中...' : '提交巡查记录',
                    style: const TextStyle(fontSize: 16),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
