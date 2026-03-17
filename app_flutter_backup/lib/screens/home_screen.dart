import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/index.dart';
import '../providers/index.dart';
import '../services/index.dart';
import 'inspection_detail_screen.dart';

/// 主屏幕/首屏
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  late LocationService _locationService;
  bool _isLoadingLocation = false;

  @override
  void initState() {
    super.initState();
    _locationService = LocationService();
    _initializeLocation();
  }

  Future<void> _initializeLocation() async {
    setState(() => _isLoadingLocation = true);
    
    try {
      // 请求位置权限
      final hasPermission = await _locationService.requestLocationPermission();
      if (!hasPermission) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('需要位置权限来获取附近的文物点')),
          );
        }
        setState(() => _isLoadingLocation = false);
        return;
      }

      // 获取当前位置
      final position = await _locationService.getCurrentLocation();
      if (position != null && mounted) {
        ref.read(nearbyHeritagesProvider.notifier).fetchNearbyHeritages(
          latitude: position.latitude,
          longitude: position.longitude,
          radiusKm: 5.0,
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('获取位置失败: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isLoadingLocation = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final heritageState = ref.watch(nearbyHeritagesProvider);
    final authState = ref.watch(authStateProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('文物巡查'),
        elevation: 2,
        actions: [
          PopupMenuButton(
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'profile',
                child: Row(
                  children: [
                    Icon(Icons.person),
                    SizedBox(width: 12),
                    Text('个人信息'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'history',
                child: Row(
                  children: [
                    Icon(Icons.history),
                    SizedBox(width: 12),
                    Text('巡查历史'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'logout',
                child: Row(
                  children: [
                    Icon(Icons.logout),
                    SizedBox(width: 12),
                    Text('登出'),
                  ],
                ),
              ),
            ],
            onSelected: (value) {
              if (value == 'logout') {
                ref.read(authStateProvider.notifier).logout();
                Navigator.of(context).pushReplacementNamed('/login');
              } else if (value == 'history') {
                Navigator.of(context).pushNamed('/history');
              }
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => _initializeLocation(),
        child: heritageState.isLoading
            ? const Center(child: CircularProgressIndicator())
            : heritageState.heritages.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.location_off,
                          size: 48,
                          color: Colors.grey[400],
                        ),
                        const SizedBox(height: 16),
                        Text(
                          heritageState.error ?? '附近没有发现文物点',
                          style: TextStyle(
                            fontSize: 16,
                            color: Colors.grey[600],
                          ),
                        ),
                        const SizedBox(height: 24),
                        ElevatedButton.icon(
                          onPressed: _initializeLocation,
                          icon: const Icon(Icons.refresh),
                          label: const Text('重新加载'),
                        ),
                        const SizedBox(height: 12),
                        TextButton.icon(
                          onPressed: () {
                            Navigator.of(context).pushNamed('/map');
                          },
                          icon: const Icon(Icons.map),
                          label: const Text('手动选择文物点'),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    itemCount: heritageState.heritages.length,
                    itemBuilder: (context, index) {
                      final heritage = heritageState.heritages[index];
                      return HeritageCard(
                        heritage: heritage,
                        onTap: () {
                          Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (context) =>
                                  InspectionDetailScreen(heritage: heritage),
                            ),
                          );
                        },
                      );
                    },
                  ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _initializeLocation,
        tooltip: '刷新位置',
        child: _isLoadingLocation
            ? const SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              )
            : const Icon(Icons.refresh),
      ),
    );
  }
}

/// 文物点卡片组件
class HeritageCard extends StatelessWidget {
  final HeritageSite heritage;
  final VoidCallback onTap;

  const HeritageCard({
    Key? key,
    required this.heritage,
    required this.onTap,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: ListTile(
        contentPadding: const EdgeInsets.all(16),
        leading: CircleAvatar(
          backgroundColor: Colors.blue[100],
          child: Icon(
            Icons.location_on,
            color: Colors.blue[700],
          ),
        ),
        title: Text(
          heritage.name,
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 8),
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.blue[50],
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    heritage.getCategoryName(),
                    style: const TextStyle(fontSize: 12),
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.green[50],
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    heritage.getLevelName(),
                    style: const TextStyle(fontSize: 12),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              heritage.address,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: 12, color: Colors.grey[600]),
            ),
            if (heritage.distanceFromUser != null) ...[
              const SizedBox(height: 4),
              Text(
                '距离: ${heritage.distanceFromUser!.toStringAsFixed(2)} km',
                style: TextStyle(fontSize: 12, color: Colors.orange[700]),
              ),
            ],
          ],
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}
