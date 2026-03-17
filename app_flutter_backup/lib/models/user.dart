/// 用户数据模型
class User {
  final int id;
  final String username;
  final String email;
  final String firstName;
  final String lastName;
  final bool isStaff;
  final List<String> permissions;
  final String? userGroup;
  final String? department;

  User({
    required this.id,
    required this.username,
    required this.email,
    required this.firstName,
    required this.lastName,
    this.isStaff = false,
    this.permissions = const [],
    this.userGroup,
    this.department,
  });

  /// 从 JSON 创建对象
  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as int,
      username: json['username'] as String? ?? '',
      email: json['email'] as String? ?? '',
      firstName: json['first_name'] as String? ?? '',
      lastName: json['last_name'] as String? ?? '',
      isStaff: json['is_staff'] as bool? ?? false,
      permissions: List<String>.from(json['permissions'] as List? ?? []),
      userGroup: json['user_group'] as String?,
      department: json['department'] as String?,
    );
  }

  /// 转换为 JSON
  Map<String, dynamic> toJson() => {
        'id': id,
        'username': username,
        'email': email,
        'first_name': firstName,
        'last_name': lastName,
        'is_staff': isStaff,
        'permissions': permissions,
        'user_group': userGroup,
        'department': department,
      };

  /// 获取用户全名
  String getFullName() => '$firstName$lastName'.trim();

  /// 检查用户是否有特定权限
  bool hasPermission(String permission) {
    return permissions.contains(permission);
  }
}

/// 登录响应模型
class LoginResponse {
  final String token;
  final User user;

  LoginResponse({
    required this.token,
    required this.user,
  });

  /// 从 JSON 创建对象
  factory LoginResponse.fromJson(Map<String, dynamic> json) {
    return LoginResponse(
      token: json['token'] as String? ?? '',
      user: User.fromJson(json['user'] as Map<String, dynamic>? ?? {}),
    );
  }

  /// 转换为 JSON
  Map<String, dynamic> toJson() => {
        'token': token,
        'user': user.toJson(),
      };
}
