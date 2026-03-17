import 'package:geolocator/geolocator.dart';

/// 位置服务类
class LocationService {
  /// 请求位置权限
  Future<bool> requestLocationPermission() async {
    final permission = await Geolocator.requestPermission();
    return permission == LocationPermission.whileInUse ||
        permission == LocationPermission.always;
  }

  /// 检查位置权限
  Future<bool> hasLocationPermission() async {
    final permission = await Geolocator.checkPermission();
    return permission == LocationPermission.whileInUse ||
        permission == LocationPermission.always;
  }

  /// 检查GPS是否启用
  Future<bool> isLocationServiceEnabled() async {
    return Geolocator.isLocationServiceEnabled();
  }

  /// 启用定位服务
  Future<bool> enableLocationService() async {
    return Geolocator.openLocationSettings();
  }

  /// 获取当前位置
  Future<Position?> getCurrentLocation() async {
    try {
      final hasPermission = await hasLocationPermission();
      if (!hasPermission) {
        return null;
      }

      final isEnabled = await isLocationServiceEnabled();
      if (!isEnabled) {
        return null;
      }

      final position = await Geolocator.getCurrentPosition();
      return position;
    } catch (e) {
      return null;
    }
  }

  /// 获取位置流（实时位置更新）
  Stream<Position> getLocationStream() {
    return Geolocator.getPositionStream();
  }

  /// 计算两点间的距离（单位：米）
  static double getDistance({
    required double lat1,
    required double lon1,
    required double lat2,
    required double lon2,
  }) {
    return Geolocator.distanceBetween(lat1, lon1, lat2, lon2);
  }

  /// 计算两点间的距离（单位：千米）
  static double getDistanceInKm({
    required double lat1,
    required double lon1,
    required double lat2,
    required double lon2,
  }) {
    return getDistance(
          lat1: lat1,
          lon1: lon1,
          lat2: lat2,
          lon2: lon2,
        ) /
        1000;
  }

  /// 判断用户是否在文物点附近
  static bool isNearby({
    required double userLat,
    required double userLon,
    required double siteLat,
    required double siteLon,
    double radiusInMeters = 100,
  }) {
    final distance = getDistance(
      lat1: userLat,
      lon1: userLon,
      lat2: siteLat,
      lon2: siteLon,
    );
    return distance <= radiusInMeters;
  }
}

/// 位置数据
class LocationData {
  final double latitude;
  final double longitude;
  final double accuracy;
  final DateTime timestamp;

  LocationData({
    required this.latitude,
    required this.longitude,
    required this.accuracy,
    required this.timestamp,
  });

  /// 从Position创建
  factory LocationData.fromPosition(Position position) {
    return LocationData(
      latitude: position.latitude,
      longitude: position.longitude,
      accuracy: position.accuracy,
      timestamp: position.timestamp ?? DateTime.now(),
    );
  }

  /// 转换为JSON
  Map<String, dynamic> toJson() => {
        'latitude': latitude,
        'longitude': longitude,
        'accuracy': accuracy,
        'timestamp': timestamp.toIso8601String(),
      };
}
