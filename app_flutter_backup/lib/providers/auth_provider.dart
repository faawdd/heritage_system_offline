import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/index.dart';
import '../services/index.dart';

/// 全局服务提供者
final apiServiceProvider = Provider((ref) {
  final service = ApiService();
  service.init();
  return service;
});
final storageServiceProvider = Provider((ref) => StorageService());
final locationServiceProvider = Provider((ref) => LocationService());
final cameraServiceProvider = Provider((ref) => CameraService());

/// 认证状态
class AuthState {
  final User? user;
  final String? token;
  final bool isLoading;
  final String? error;

  AuthState({
    this.user,
    this.token,
    this.isLoading = false,
    this.error,
  });

  bool get isAuthenticated => token != null && user != null;

  AuthState copyWith({
    User? user,
    String? token,
    bool? isLoading,
    String? error,
  }) {
    return AuthState(
      user: user ?? this.user,
      token: token ?? this.token,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

/// 认证状态提供者
final authStateProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref);
});

/// 认证业务逻辑
class AuthNotifier extends StateNotifier<AuthState> {
  final Ref ref;
  AuthNotifier(this.ref) : super(AuthState()) {
    _init();
  }

  /// 初始化
  Future<void> _init() async {
    // 检查是否已登录
    // 可以从SharedPreferences恢复登录状态
  }

  /// 登录
  Future<bool> login(String username, String password) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final apiService = ref.read(apiServiceProvider);
      final response = await apiService.login(
        username: username,
        password: password,
      );
      // 登录成功后，立即更新状态
      state = AuthState(
        user: response.user,
        token: response.token,
        isLoading: false,
      );
      return true;
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: e.toString(),
      );
      return false;
    }
  }

  /// 登出
  Future<void> logout() async {
    final apiService = ref.read(apiServiceProvider);
    await apiService.logout();
    state = AuthState();
  }
}
