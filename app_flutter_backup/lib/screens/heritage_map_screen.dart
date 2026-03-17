import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/index.dart';
import '../providers/index.dart';
import '../config/api_config.dart';
import 'inspection_detail_screen.dart';

// 图层类型枚举
enum MapLayerType {
  vec('矢量地图'),
  image('影像地图'),
  terrain('地形地图');

  final String label;
  const MapLayerType(this.label);
}

final allHeritagesProvider = FutureProvider<List<HeritageSite>>((ref) async {
  final apiService = ref.watch(apiServiceProvider);
  final locationService = ref.watch(locationServiceProvider);
  
  try {
    // 获取当前位置
    final location = await locationService.getCurrentLocation();
    if (location != null) {
      // 使用一个很大的半径来获取"所有"文物点
      return apiService.getNearbyHeritages(
        latitude: location.latitude,
        longitude: location.longitude,
        radiusKm: 9999,
      );
    }
  } catch (e) {
    print('Failed to get location: $e');
  }
  
  // 如果定位失败，返回空列表
  return [];
});

class HeritageMapScreen extends ConsumerStatefulWidget {
  const HeritageMapScreen({Key? key}) : super(key: key);

  @override
  ConsumerState<HeritageMapScreen> createState() => _HeritageMapScreenState();
}

class _HeritageMapScreenState extends ConsumerState<HeritageMapScreen> {
  MapLayerType _selectedLayer = MapLayerType.vec;
  late MapController _mapController;

  @override
  void initState() {
    super.initState();
    _mapController = MapController();
  }

  String _getTdtUrl(MapLayerType layer) {
    switch (layer) {
      case MapLayerType.vec:
        return ApiConfig.tdtVecUrl.replaceAll('{s}', '0');
      case MapLayerType.image:
        return ApiConfig.tdtImageUrl.replaceAll('{s}', '0');
      case MapLayerType.terrain:
        return ApiConfig.tdtImageUrl.replaceAll('{s}', '0');
    }
  }

  String _getCvaUrl() {
    return ApiConfig.tdtCvaUrl.replaceAll('{s}', '0');
  }

  @override
  Widget build(BuildContext context) {
    final heritagesAsync = ref.watch(allHeritagesProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('手动选择文物点'),
        actions: [
          PopupMenuButton<MapLayerType>(
            onSelected: (MapLayerType layer) {
              setState(() {
                _selectedLayer = layer;
              });
            },
            itemBuilder: (BuildContext context) =>
                <PopupMenuEntry<MapLayerType>>[
              for (final layer in MapLayerType.values)
                PopupMenuItem<MapLayerType>(
                  value: layer,
                  child: Text(layer.label),
                ),
            ],
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Center(
                child: Text(
                  '图层: ${_selectedLayer.label}',
                  style: const TextStyle(color: Colors.white),
                ),
              ),
            ),
          ),
        ],
      ),
      body: heritagesAsync.when(
        data: (heritages) {
          if (heritages.isEmpty) {
            return const Center(child: Text('没有可用的文物点数据。'));
          }

          // 按距离排序
          heritages.sort((a, b) {
            final distA = a.distanceFromUser ?? double.maxFinite;
            final distB = b.distanceFromUser ?? double.maxFinite;
            return distA.compareTo(distB);
          });

          final centerPoint =
              LatLng(heritages.first.latitude, heritages.first.longitude);

          return Stack(
            children: [
              FlutterMap(
                mapController: _mapController,
                options: MapOptions(
                  initialCenter: centerPoint,
                  initialZoom: 13.0,
                ),
                children: [
                  TileLayer(
                    urlTemplate: _getTdtUrl(_selectedLayer),
                    userAgentPackageName: 'com.example.heritage',
                    subdomains: const ['0', '1', '2', '3', '4', '5', '6', '7'],
                  ),
                  // 标签图层
                  TileLayer(
                    urlTemplate: _getCvaUrl(),
                    userAgentPackageName: 'com.example.heritage',
                    subdomains: const ['0', '1', '2', '3', '4', '5', '6', '7'],
                  ),
                  MarkerLayer(
                    markers: heritages.map((site) {
                      return Marker(
                        point:
                            LatLng(site.latitude, site.longitude),
                        width: 80.0,
                        height: 80.0,
                        child: GestureDetector(
                          onTap: () {
                            _showSiteDetails(context, site);
                          },
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.location_on,
                                  color: Colors.red, size: 40),
                              Text(
                                site.name,
                                style: const TextStyle(
                                  color: Colors.black,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 10,
                                  backgroundColor: Colors.white,
                                ),
                                textAlign: TextAlign.center,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ],
              ),
              // 右侧文物点列表
              Positioned(
                right: 0,
                top: 0,
                bottom: 0,
                width: 250,
                child: Container(
                  color: Colors.white.withOpacity(0.95),
                  child: ListView.builder(
                    itemCount: heritages.length,
                    itemBuilder: (context, index) {
                      final site = heritages[index];
                      return ListTile(
                        leading: const Icon(Icons.location_on,
                            color: Colors.blue, size: 20),
                        title: Text(
                          site.name,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 12),
                        ),
                        subtitle: Text(
                          site.distanceFromUser != null
                              ? '距离: ${site.distanceFromUser!.toStringAsFixed(2)} km'
                              : '距离: 未知',
                          style: const TextStyle(fontSize: 11, color: Colors.orange),
                        ),
                        onTap: () {
                          // 地图平移到该标记
                          _mapController.move(
                            LatLng(site.latitude, site.longitude),
                            15.0,
                          );
                          // 显示详情
                          _showSiteDetails(context, site);
                        },
                      );
                    },
                  ),
                ),
              ),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, stack) => Center(child: Text('加载失败: $err')),
      ),
    );
  }

  void _showSiteDetails(BuildContext context, HeritageSite site) {
    showModalBottomSheet(
      context: context,
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                site.name,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text('地址: ${site.address}'),
              const SizedBox(height: 8),
              Text('保护级别: ${site.getLevelName()}'),
              if (site.distanceFromUser != null) ...[
                const SizedBox(height: 8),
                Text(
                  '距离: ${site.distanceFromUser!.toStringAsFixed(2)} km',
                  style: const TextStyle(
                    fontSize: 14,
                    color: Colors.orange,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () {
                  Navigator.pop(context);
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) =>
                          InspectionDetailScreen(heritage: site),
                    ),
                  );
                },
                child: const Text('选择并开始巡查'),
              ),
            ],
          ),
        );
      },
    );
  }
}
