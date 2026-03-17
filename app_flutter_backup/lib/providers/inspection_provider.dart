import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/index.dart';
import 'auth_provider.dart';

/// 巡查记录列表状态
class InspectionListState {
  final List<InspectionRecord> records;
  final bool isLoading;
  final String? error;
  final DateTime? lastUpdated;

  InspectionListState({
    this.records = const [],
    this.isLoading = false,
    this.error,
    this.lastUpdated,
  });

  InspectionListState copyWith({
    List<InspectionRecord>? records,
    bool? isLoading,
    String? error,
    DateTime? lastUpdated,
  }) {
    return InspectionListState(
      records: records ?? this.records,
      isLoading: isLoading ?? this.isLoading,
      error: error,
      lastUpdated: lastUpdated ?? this.lastUpdated,
    );
  }
}

/// 我的巡查记录提供者
final myInspectionsProvider =
    StateNotifierProvider<MyInspectionsNotifier, InspectionListState>((ref) {
  return MyInspectionsNotifier(ref);
});

/// 我的巡查记录业务逻辑
class MyInspectionsNotifier extends StateNotifier<InspectionListState> {
  final Ref ref;
  MyInspectionsNotifier(this.ref) : super(InspectionListState());

  /// 获取我的巡查记录
  Future<void> fetchMyInspections({
    int page = 1,
    int pageSize = 20,
  }) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final apiService = ref.read(apiServiceProvider);
      final records = await apiService.getMyInspections(
        page: page,
        pageSize: pageSize,
      );
      state = state.copyWith(
        records: records,
        isLoading: false,
        lastUpdated: DateTime.now(),
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: e.toString(),
      );
    }
  }

  /// 从本地加载
  Future<void> loadFromLocal() async {
    try {
      final storageService = ref.read(storageServiceProvider);
      final records = await storageService.getAllRecords();
      state = state.copyWith(records: records);
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  /// 创建新记录
  Future<bool> createInspection({
    required int siteId,
    required String siteName,
    required bool isNormal,
    String? issueDetails,
    String? photoPath,
    double? latitude,
    double? longitude,
  }) async {
    try {
      final storageService = ref.read(storageServiceProvider);
      final record = InspectionRecord(
        siteId: siteId,
        siteName: siteName,
        isNormal: isNormal,
        issueDetails: issueDetails,
        photoPath: photoPath,
        latitude: latitude,
        longitude: longitude,
        inspectTime: DateTime.now(),
      );

      await storageService.saveInspectionRecord(record);
      
      // 立即同步到服务器
      await _syncToServer(record);
      
      // 刷新列表
      await loadFromLocal();
      return true;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return false;
    }
  }

  /// 同步到服务器
  /// 
  /// 功能：
  /// 1. 根据是否有照片选择上传方式
  /// 2. 上传成功后标记记录为已上传 ✅ 关键修复
  /// 3. 上传失败时保留本地记录供稍后重试
  Future<void> _syncToServer(InspectionRecord record) async {
    try {
      final apiService = ref.read(apiServiceProvider);
      
      // 📤 执行上传
      if (record.photoPath != null && record.photoPath!.isNotEmpty) {
        // 有照片：使用FormData上传（包含photo文件）
        print('📸 使用FormData上传（含照片）: ${record.siteId}');
        await apiService.uploadInspectionPhoto(
          siteId: record.siteId,
          photoPath: record.photoPath!,
          isNormal: record.isNormal,
          issueDetails: record.issueDetails,
          latitude: record.latitude,
          longitude: record.longitude,
        );
      } else {
        // 无照片：使用JSON上传
        print('📝 使用JSON上传（无照片）: ${record.siteId}');
        await apiService.createInspection(
          siteId: record.siteId,
          isNormal: record.isNormal,
          issueDetails: record.issueDetails,
          latitude: record.latitude,
          longitude: record.longitude,
        );
      }
      
      // ✅ 上传成功！标记为已上传（关键修复）
      if (record.id != null) {
        final storageService = ref.read(storageServiceProvider);
        await storageService.markRecordAsUploaded(record.id!, null);
        print('✅ 记录 ${record.id} 已标记为上传成功 (site: ${record.siteId})');
      }
      
    } catch (e) {
      // ❌ 上传失败：保持本地记录，用户可点击"同步"重试
      print('❌ 记录 ${record.id} 同步失败: $e');
    }
  }

  /// 同步未上传的记录
  /// 返回同步结果供UI显示、包含详细错误信息
  Future<Map<String, dynamic>> syncUnuploadedRecords() async {
    final result = {
      'total': 0,
      'success': 0,
      'failed': 0,
      'errors': <String>[],  // 新增：记录所有错误
    };
    
    try {
      final storageService = ref.read(storageServiceProvider);
      final unupload = await storageService.getUnuploadedRecords();
      
      result['total'] = unupload.length;
      print('🔄 开始同步 ${result['total']} 条未上传的记录...');

      if (result['total'] == 0) {
        print('📭 没有待同步的记录');
        return result;
      }

      for (final record in unupload) {
        try {
          final apiService = ref.read(apiServiceProvider);
          
          print('📤 同步记录 ${record.id} (文物点: ${record.siteId})...');
          
          if (record.photoPath != null && record.photoPath!.isNotEmpty) {
            // 有照片：FormData上传
            print('📸 使用FormData上传（包含照片）');
            await apiService.uploadInspectionPhoto(
              siteId: record.siteId,
              photoPath: record.photoPath!,
              isNormal: record.isNormal,
              issueDetails: record.issueDetails,
              latitude: record.latitude,
              longitude: record.longitude,
            );
          } else {
            // 无照片：JSON上传
            print('📝 使用JSON上传（无照片）');
            await apiService.createInspection(
              siteId: record.siteId,
              isNormal: record.isNormal,
              issueDetails: record.issueDetails,
              latitude: record.latitude,
              longitude: record.longitude,
            );
          }
          
          // ✅ 标记为已上传
          if (record.id != null) {
            await storageService.markRecordAsUploaded(record.id!, null);
            result['success'] = ((result['success'] as int?) ?? 0) + 1;
            print('✅ 记录 ${record.id} 同步成功');
          }
        } catch (e) {
          // ❌ 此条记录上传失败，继续下一条
          result['failed'] = ((result['failed'] as int?) ?? 0) + 1;
          final errorMsg = e.toString();
          (result['errors'] as List).add('记录${record.id}: $errorMsg');
          print('❌ 记录 ${record.id} 同步失败: $e');
        }
      }
      
    } catch (e) {
      print('❌ 批量同步异常: $e');
      (result['errors'] as List).add('批量同步异常: $e');
      state = state.copyWith(error: e.toString());
    }
    
    // 打印最终统计
    print('═════ 同步完成统计 ═════');
    print('📊 总计: ${result['total']}');
    print('✅ 成功: ${result['success']}');
    print('❌ 失败: ${result['failed']}');
    
    if ((result['errors'] as List).isNotEmpty) {
      print('💡 错误详情:');
      for (final error in (result['errors'] as List)) {
        print('  - $error');
      }
    }
    print('═════════════════════════');
    
    return result;
  }
}

/// 本地未上传的巡查记录提供者
final unuploadedInspectionsProvider = FutureProvider((ref) async {
  final storageService = ref.read(storageServiceProvider);
  return storageService.getUnuploadedRecords();
});
