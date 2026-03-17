/// 巡查记录数据模型
class InspectionRecord {
  final int? id;
  final int siteId;
  final String siteName;
  final String? photoPath; // 本地文件路径或远程URL
  final double? latitude;
  final double? longitude;
  final DateTime inspectTime;
  final bool isNormal;
  final String? issueDetails;
  final bool uploadedToServer;
  final String? serverPhotoUrl;

  InspectionRecord({
    this.id,
    required this.siteId,
    required this.siteName,
    this.photoPath,
    this.latitude,
    this.longitude,
    required this.inspectTime,
    this.isNormal = true,
    this.issueDetails,
    this.uploadedToServer = false,
    this.serverPhotoUrl,
  });

  /// 从 JSON 创建对象（带安全的类型转换）
  factory InspectionRecord.fromJson(Map<String, dynamic> json) {
    // 安全的 int 转换，处理 String id 的情况
    int? parseId(dynamic value) {
      if (value == null) return null;
      if (value is int) return value;
      if (value is String) return int.tryParse(value);
      return null;
    }

    // 安全的 int 转换，处理 site 可能是 String 的情况
    int parseSite(dynamic value) {
      if (value is int) return value;
      if (value is String) return int.tryParse(value) ?? 0;
      return 0;
    }

    return InspectionRecord(
      id: parseId(json['id']),
      siteId: parseSite(json['site']),
      siteName: json['site_name'] as String? ?? '',
      photoPath: json['photo'] as String?,
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      inspectTime: DateTime.parse(json['inspect_time'] as String),
      isNormal: json['is_normal'] as bool? ?? true,
      issueDetails: json['issue_details'] as String?,
      uploadedToServer: json['uploaded'] as bool? ?? false,
      serverPhotoUrl: json['server_photo_url'] as String?,
    );
  }

  /// 转换为 JSON（用于本地存储）
  Map<String, dynamic> toJson() => {
        'id': id,
        'site': siteId,
        'site_name': siteName,
        'photo': photoPath,
        'latitude': latitude,
        'longitude': longitude,
        'inspect_time': inspectTime.toIso8601String(),
        'is_normal': isNormal,
        'issue_details': issueDetails,
        'uploaded': uploadedToServer,
        'server_photo_url': serverPhotoUrl,
      };

  /// 转换为表单数据（用于上传）
  Map<String, dynamic> toFormData() => {
        'site': siteId,
        'photo': photoPath,
        'latitude': latitude,
        'longitude': longitude,
        'is_normal': isNormal,
        'issue_details': issueDetails ?? '',
      };

  /// 创建副本并修改指定属性
  InspectionRecord copyWith({
    int? id,
    int? siteId,
    String? siteName,
    String? photoPath,
    double? latitude,
    double? longitude,
    DateTime? inspectTime,
    bool? isNormal,
    String? issueDetails,
    bool? uploadedToServer,
    String? serverPhotoUrl,
  }) {
    return InspectionRecord(
      id: id ?? this.id,
      siteId: siteId ?? this.siteId,
      siteName: siteName ?? this.siteName,
      photoPath: photoPath ?? this.photoPath,
      latitude: latitude ?? this.latitude,
      longitude: longitude ?? this.longitude,
      inspectTime: inspectTime ?? this.inspectTime,
      isNormal: isNormal ?? this.isNormal,
      issueDetails: issueDetails ?? this.issueDetails,
      uploadedToServer: uploadedToServer ?? this.uploadedToServer,
      serverPhotoUrl: serverPhotoUrl ?? this.serverPhotoUrl,
    );
  }
}
