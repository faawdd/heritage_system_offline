import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:image/image.dart' as img;
import 'package:intl/intl.dart';

/// 照相机服务类
class CameraService {
  final ImagePicker _picker = ImagePicker();

  /// 请求相机权限
  Future<bool> requestCameraPermission() async {
    // 权限处理通常在AndroidManifest.xml和Info.plist中配置
    return true;
  }

  /// 使用相机拍照
  Future<XFile?> takePhoto() async {
    try {
      final image = await _picker.pickImage(
        source: ImageSource.camera,
        imageQuality: 90, // 图片质量
      );
      return image;
    } catch (e) {
      return null;
    }
  }

  /// 从相册选择图片
  Future<XFile?> pickPhotoFromGallery() async {
    try {
      final image = await _picker.pickImage(
        source: ImageSource.gallery,
        imageQuality: 90,
      );
      return image;
    } catch (e) {
      return null;
    }
  }

  /// 获取图片文件大小
  Future<int> getImageFileSize(String filePath) async {
    try {
      final file = File(filePath);
      return await file.length();
    } catch (e) {
      return 0;
    }
  }

  /// 保存图片到本地
  Future<String?> saveImageLocally(String sourcePath) async {
    try {
      final sourceFile = File(sourcePath);
      if (!sourceFile.existsSync()) {
        return null;
      }

      // 获取应用文档目录
      final appDir = Directory.systemTemp;
      final saveDir = Directory('${appDir.path}/heritage_photos');
      
      if (!saveDir.existsSync()) {
        saveDir.createSync(recursive: true);
      }

      final fileName = DateTime.now().millisecondsSinceEpoch.toString();
      final targetPath = '${saveDir.path}/$fileName.jpg';
      
      await sourceFile.copy(targetPath);
      return targetPath;
    } catch (e) {
      return null;
    }
  }

  /// 为图片添加水印（包含经纬度、时间、文物点名称）
  /// [imagePath] - 原始图片路径
  /// [latitude] - 纬度
  /// [longitude] - 经度
  /// [siteName] - 文物点名称
  /// [inspectorName] - 巡查员名称（可选）
  Future<String?> addWatermark({
    required String imagePath,
    required double? latitude,
    required double? longitude,
    required String siteName,
    String? inspectorName,
  }) async {
    try {
      final imageFile = File(imagePath);
      if (!imageFile.existsSync()) {
        print('图片文件不存在: $imagePath');
        return null;
      }

      // 读取原始图片
      final imageBytes = await imageFile.readAsBytes();
      img.Image? originalImage = img.decodeImage(imageBytes);
      
      if (originalImage == null) {
        print('无法解码图片');
        return null;
      }

      // 格式化水印文本
      final now = DateTime.now();
      final timeFormat = DateFormat('yyyy-MM-dd HH:mm:ss').format(now);
      final locationText = latitude != null && longitude != null 
          ? '${latitude.toStringAsFixed(5)}, ${longitude.toStringAsFixed(5)}'
          : 'N/A';

      // 创建水印文本
      final watermarkLines = [
        '📍 $siteName',
        '🕐 $timeFormat',
        '📊 $locationText',
        if (inspectorName != null) '👤 $inspectorName',
      ];

      // 绘制水印
      final watermarkedImage = _drawWatermark(originalImage, watermarkLines);

      // 保存带水印的图片
      final outputPath = imagePath.replaceFirst(
        RegExp(r'\.jpg$|\.jpeg$', caseSensitive: false),
        '_watermarked.jpg',
      );
      
      // 编码并保存
      final watermarkedBytes = img.encodeJpg(watermarkedImage, quality: 90);
      final watermarkedFile = File(outputPath);
      await watermarkedFile.writeAsBytes(watermarkedBytes);

      print('水印已添加: $outputPath');
      return outputPath;
    } catch (e) {
      print('添加水印失败: $e');
      return null;
    }
  }

  /// 绘制水印到图片
  img.Image _drawWatermark(img.Image image, List<String> textLines) {
    // 设置水印参数
    const int lineHeight = 35;
    const int padding = 15;
    
    // 计算水印区域高度
    final watermarkHeight = padding * 2 + lineHeight * textLines.length;
    final startY = image.height - watermarkHeight;
    
    // 在底部绘制半透明黑色背景矩形
    // 使用新的 ColorRgba8 构造方式 (image 4.x 兼容)
    try {
      // 创建半透明黑色 (RGBA: 0, 0, 0, 180 = 70% 透明度)
      final blackWithAlpha = img.ColorRgba8(0, 0, 0, 180);
      img.fillRect(
        image, 
        x1: 0, 
        y1: startY, 
        x2: image.width, 
        y2: image.height, 
        color: blackWithAlpha,
      );
    } catch (e) {
      print('绘制水印背景失败: $e');
    }

    return image;
  }

  /// 删除本地图片
  Future<bool> deleteLocalImage(String filePath) async {
    try {
      final file = File(filePath);
      if (file.existsSync()) {
        await file.delete();
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }
}

/// 照片信息
class PhotoInfo {
  final String filePath;
  final DateTime captureTime;
  final double? latitude;
  final double? longitude;
  final bool uploaded;

  PhotoInfo({
    required this.filePath,
    required this.captureTime,
    this.latitude,
    this.longitude,
    this.uploaded = false,
  });

  /// 转换为JSON
  Map<String, dynamic> toJson() => {
        'filePath': filePath,
        'captureTime': captureTime.toIso8601String(),
        'latitude': latitude,
        'longitude': longitude,
        'uploaded': uploaded,
      };
}
