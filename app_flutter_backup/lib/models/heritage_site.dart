/// 文物点数据模型
class HeritageSite {
  final int id;
  final String name;
  final String sipCode;
  final String category;
  final String level;
  final String address;
  final double longitude;
  final double latitude;
  final String description;
  final String manager;
  final double? distanceFromUser; // 距离用户的距离（km）

  HeritageSite({
    required this.id,
    required this.name,
    required this.sipCode,
    required this.category,
    required this.level,
    required this.address,
    required this.longitude,
    required this.latitude,
    required this.description,
    required this.manager,
    this.distanceFromUser,
  });

  /// 从 JSON 创建对象
  factory HeritageSite.fromJson(Map<String, dynamic> json) {
    return HeritageSite(
      id: json['id'] as int,
      name: json['name'] as String? ?? '',
      sipCode: json['sip_code'] as String? ?? '',
      category: json['category'] as String? ?? '',
      level: json['level'] as String? ?? '',
      address: json['address'] as String? ?? '',
      longitude: (json['longitude'] as num?)?.toDouble() ?? 0.0,
      latitude: (json['latitude'] as num?)?.toDouble() ?? 0.0,
      description: json['description'] as String? ?? '',
      manager: json['manager'] as String? ?? '',
      distanceFromUser: (json['distance'] as num?)?.toDouble(),
    );
  }

  /// 转换为 JSON
  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'sip_code': sipCode,
        'category': category,
        'level': level,
        'address': address,
        'longitude': longitude,
        'latitude': latitude,
        'description': description,
        'manager': manager,
        'distance': distanceFromUser,
      };

  /// 获取类别名称
  String getCategoryName() {
    const categories = {
      'GYZ': '古文化遗址',
      'GMZ': '古墓葬',
      'GJZ': '古建筑',
      'SKT': '石窟寺及石刻',
      'JDJW': '近现代重要史迹及代表性建筑',
      'QT': '其他',
    };
    return categories[category] ?? category;
  }

  /// 获取保护级别名称
  String getLevelName() {
    const levels = {
      'GB': '全国重点文物保护单位',
      'SB': '自治区级文物保护单位',
      'XB': '县级文物保护单位',
      'DS': '尚未定级的不可移动文物',
    };
    return levels[level] ?? level;
  }
}
