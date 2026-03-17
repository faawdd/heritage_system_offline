import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/index.dart';
import 'auth_provider.dart';

/// 文物点列表状态
class HeritageListState {
  final List<HeritageSite> heritages;
  final bool isLoading;
  final String? error;
  final DateTime? lastUpdated;

  HeritageListState({
    this.heritages = const [],
    this.isLoading = false,
    this.error,
    this.lastUpdated,
  });

  HeritageListState copyWith({
    List<HeritageSite>? heritages,
    bool? isLoading,
    String? error,
    DateTime? lastUpdated,
  }) {
    return HeritageListState(
      heritages: heritages ?? this.heritages,
      isLoading: isLoading ?? this.isLoading,
      error: error,
      lastUpdated: lastUpdated ?? this.lastUpdated,
    );
  }
}

/// 附近文物点提供者
final nearbyHeritagesProvider =
    StateNotifierProvider<NearbyHeritagesNotifier, HeritageListState>((ref) {
  return NearbyHeritagesNotifier(ref);
});

/// 附近文物点业务逻辑
class NearbyHeritagesNotifier extends StateNotifier<HeritageListState> {
  final Ref ref;
  NearbyHeritagesNotifier(this.ref) : super(HeritageListState());

  /// 获取附近的文物点
  Future<void> fetchNearbyHeritages({
    required double latitude,
    required double longitude,
    double radiusKm = 5.0,
  }) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final apiService = ref.read(apiServiceProvider);
      final heritages = await apiService.getNearbyHeritages(
        latitude: latitude,
        longitude: longitude,
        radiusKm: radiusKm,
      );

      // 缓存到本地存储
      final storageService = ref.read(storageServiceProvider);
      await storageService.cacheHeritages(heritages);

      state = state.copyWith(
        heritages: heritages,
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

  /// 从缓存加载文物点
  Future<void> loadFromCache() async {
    try {
      final storageService = ref.read(storageServiceProvider);
      final heritages = await storageService.getCachedHeritages();
      state = state.copyWith(heritages: heritages);
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  /// 清空缓存
  Future<void> clearCache() async {
    final storageService = ref.read(storageServiceProvider);
    await storageService.clearHeritageCache();
    state = state.copyWith(heritages: []);
  }
}

/// 选中的文物点提供者
final selectedHeritageProvider = StateProvider<HeritageSite?>((ref) => null);
