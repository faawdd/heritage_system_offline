import 'dart:io';
import 'package:dio/dio.dart';
import 'package:dio_smart_retry/dio_smart_retry.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config/api_config.dart';
import '../models/index.dart';

/// API 服务类
class ApiService {
  late final Dio _dio;
  late final SharedPreferences _prefs;
  String? _authToken;

  ApiService() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.baseUrl,
        connectTimeout: Duration(milliseconds: ApiConfig.connectTimeout),
        receiveTimeout: Duration(milliseconds: ApiConfig.receiveTimeout),
        sendTimeout: Duration(milliseconds: ApiConfig.sendTimeout),
        // 注意：不在这里设置contentType，让dio根据数据类型自动设置
        // JSON请求会自动设置为application/json
        // FormData请求会自动设置为multipart/form-data
      ),
    );

    // 添加重试拦截器
    _dio.httpClientAdapter;
    _dio.interceptors.add(RetryInterceptor(
      dio: _dio,
      logPrint: print,
      retries: 2,
    ));

    // 添加自定义拦截器
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (_authToken != null) {
            options.headers['Authorization'] = 'Bearer $_authToken';
          }
          return handler.next(options);
        },
        onError: (error, handler) {
          if (error.response?.statusCode == 401) {
            _authToken = null;
            _prefs.remove(ApiConfig.tokenKey);
          }
          return handler.next(error);
        },
      ),
    );
  }

  /// 初始化服务
  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
    _authToken = _prefs.getString(ApiConfig.tokenKey);
  }

  /// 保存认证令牌
  Future<void> _saveToken(String token) async {
    _authToken = token;
    await _prefs.setString(ApiConfig.tokenKey, token);
  }

  /// 清除认证令牌
  Future<void> _clearToken() async {
    _authToken = null;
    await _prefs.remove(ApiConfig.tokenKey);
  }

  /// 用户登录
  Future<LoginResponse> login({
    required String username,
    required String password,
  }) async {
    try {
      final response = await _dio.post(
        ApiConfig.loginEndpoint,
        data: {
          'username': username,
          'password': password,
        },
      );

      final loginData = LoginResponse.fromJson(response.data);
      await _saveToken(loginData.token);
      await _prefs.setString(
        ApiConfig.userDataKey,
        loginData.user.toJson().toString(),
      );
      return loginData;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// 获取当前用户信息
  Future<User> getCurrentUser() async {
    try {
      final response = await _dio.get(ApiConfig.userEndpoint);
      return User.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// 用户登出
  Future<void> logout() async {
    await _clearToken();
  }

  /// 获取附近的文物点
  Future<List<HeritageSite>> getNearbyHeritages({
    required double latitude,
    required double longitude,
    double radiusKm = 5.0,
  }) async {
    try {
      final response = await _dio.get(
        ApiConfig.nearbyHeritagesEndpoint,
        queryParameters: {
          'latitude': latitude,
          'longitude': longitude,
          'radius': radiusKm,
        },
      );

      final data = response.data as List;
      return data.map((e) => HeritageSite.fromJson(e)).toList();
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// 创建巡查记录
  Future<InspectionRecord> createInspection({
    required int siteId,
    required bool isNormal,
    String? issueDetails,
    double? latitude,
    double? longitude,
  }) async {
    try {
      final response = await _dio.post(
        ApiConfig.createInspectionEndpoint,
        data: {
          'site': siteId,
          'is_normal': isNormal,
          'issue_details': issueDetails ?? '',
          'latitude': latitude,
          'longitude': longitude,
        },
      );

      return InspectionRecord.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// 上传巡查照片（带诊断）
  Future<InspectionRecord> uploadInspectionPhoto({
    required int siteId,
    required String photoPath,
    required bool isNormal,
    String? issueDetails,
    double? latitude,
    double? longitude,
  }) async {
    try {
      // 📋 诊断信息
      print('═════ 上传巡查照片诊断 ═════');
      print('🌐 API基础地址: ${_dio.options.baseUrl}');
      print('📝 上传端点: ${ApiConfig.createInspectionEndpoint}');
      print('🔑 认证令牌: ${_authToken != null ? "✅ 已设置" : "❌ 未设置"}');
      print('📂 照片路径: $photoPath');
      print('📍 文物点ID: $siteId');
      print('📍 位置: ($latitude, $longitude)');
      
      // 📋 检查文件存在性
      final file = File(photoPath);
      if (!file.existsSync()) {
        throw ApiException(message: '照片文件不存在: $photoPath');
      }
      
      final fileSize = file.lengthSync();
      print('📊 文件大小: ${(fileSize / 1024 / 1024).toStringAsFixed(2)}MB');
      
      // 📋 构建FormData
      print('🔨 构建FormData...');
      final formData = FormData.fromMap({
        'site': siteId,
        'is_normal': isNormal,
        'issue_details': issueDetails ?? '',
        'latitude': latitude ?? 0,
        'longitude': longitude ?? 0,
        'photo': await MultipartFile.fromFile(
          photoPath,
          filename: photoPath.split('/').last,
        ),
      });
      
      print('✅ FormData构建成功');
      print('═════ 开始上传 ═════');
      
      // 📤 执行上传
      final response = await _dio.post(
        ApiConfig.createInspectionEndpoint,
        data: formData,
        options: Options(
          headers: {
            // 让 Dio 自动设置 Content-Type: multipart/form-data
          },
        ),
      );

      print('✅ 上传成功! 状态码: ${response.statusCode}');
      print('═════════════════════════');
      
      return InspectionRecord.fromJson(response.data);
    } on DioException catch (e) {
      print('❌ 上传失败!');
      throw _handleError(e);
    } catch (e) {
      print('❌ 未知错误: $e');
      throw ApiException(message: '上传失败: $e');
    }
  }

  /// 获取我的巡查记录（带诊断）
  Future<List<InspectionRecord>> getMyInspections({
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      print('═════ 获取我的巡查记录 ═════');
      print('🌐 请求端点: ${ApiConfig.myInspectionsEndpoint}');
      print('📄 分页参数: page=$page, page_size=$pageSize');
      print('🔑 令牌: ${_authToken != null ? "已设置" : "未设置"}');
      
      final response = await _dio.get(
        ApiConfig.myInspectionsEndpoint,
        queryParameters: {
          'page': page,
          'page_size': pageSize,
        },
      );

      print('✅ 获取成功! 状态码: ${response.statusCode}');
      
      final data = response.data;
      print('📊 响应类型: ${data.runtimeType}');
      
      // 🔧 处理分页格式
      if (data is Map<String, dynamic>) {
        final results = data['results'] as List?;
        if (results == null) {
          print('❌ 响应格式错误: 缺少results字段');
          print('响应内容: ${data.toString()}');
          throw ApiException(message: '响应格式错误: 缺少results字段');
        }
        
        print('📦 返回记录数: ${results.length}');
        print('📊 总数: ${data['count']}');
        print('═════════════════════════');
        
        return results
            .map((e) => InspectionRecord.fromJson(e as Map<String, dynamic>))
            .toList();
      }
      else if (data is List) {
        print('📦 返回记录数: ${data.length}');
        print('═════════════════════════');
        
        return data
            .map((e) => InspectionRecord.fromJson(e as Map<String, dynamic>))
            .toList();
      }
      else {
        print('❌ 未知的响应格式: ${data.runtimeType}');
        print('响应内容: ${data.toString()}');
        throw ApiException(
          message: '意外的响应格式: ${data.runtimeType}',
        );
      }
    } on DioException catch (e) {
      print('❌ 获取失败!');
      throw _handleError(e);
    } catch (e) {
      print('❌ 解析错误: $e');
      throw ApiException(message: '解析响应失败: $e');
    }
  }

  /// 获取统计信息
  Future<Map<String, dynamic>> getStatistics() async {
    try {
      final response = await _dio.get(ApiConfig.statisticsEndpoint);
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// 错误处理（带详细诊断）
  Exception _handleError(DioException error) {
    print('═════ API 错误详细信息 ═════');
    print('请求URL: ${error.requestOptions.path}');
    print('请求方法: ${error.requestOptions.method}');
    print('错误类型: ${error.type}');
    
    if (error.response != null) {
      final statusCode = error.response!.statusCode ?? 500;
      final responseData = error.response!.data;
      
      print('状态码: $statusCode');
      print('响应数据: $responseData');
      
      // 根据状态码返回可读的错误信息
      String message;
      switch (statusCode) {
        case 400:
          message = '请求格式错误: ${responseData?['detail'] ?? '未知错误'}';
        case 401:
          message = '认证失败: 令牌过期或无效，请重新登录';
        case 403:
          message = '权限不足: 无权访问此资源';
        case 404:
          message = '资源不存在: ${error.requestOptions.path}';
        case 500:
          message = '服务器错误: 请稍后重试';
        default:
          message = responseData?['detail'] ?? 
                 responseData?['error'] ?? 
                 '请求失败 ($statusCode)';
      }
      
      print('错误信息: $message');
      print('═════════════════════════');
      return ApiException(
        message: message,
        statusCode: statusCode,
      );
    }
    
    // 网络错误
    String message;
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
        message = '连接超时 - 请检查网络连接和服务器地址';
      case DioExceptionType.receiveTimeout:
        message = '接收超时 - 服务器响应缓慢';
      case DioExceptionType.sendTimeout:
        message = '发送超时 - 网络不稳定';
      case DioExceptionType.unknown:
        message = '网络错误: ${error.error}';
        break;
      default:
        message = '网络错误: ${error.message ?? "未知错误"}';
    }
    
    print('网络错误: $message');
    print('═════════════════════════');
    return ApiException(message: message);
  }
}

/// API 异常
class ApiException implements Exception {
  final String message;
  final int? statusCode;

  ApiException({
    required this.message,
    this.statusCode,
  });

  @override
  String toString() => message;
}
