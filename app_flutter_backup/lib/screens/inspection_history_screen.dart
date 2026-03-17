import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../models/index.dart';
import '../providers/index.dart';

/// 巡查历史屏幕
class InspectionHistoryScreen extends ConsumerStatefulWidget {
  const InspectionHistoryScreen({Key? key}) : super(key: key);

  @override
  ConsumerState<InspectionHistoryScreen> createState() =>
      _InspectionHistoryScreenState();
}

class _InspectionHistoryScreenState
    extends ConsumerState<InspectionHistoryScreen> {
  @override
  void initState() {
    super.initState();
    _loadInspections();
  }

  Future<void> _loadInspections() async {
    ref.read(myInspectionsProvider.notifier).loadFromLocal();
  }

  Future<void> _syncRecords() async {
    final notifier = ref.read(myInspectionsProvider.notifier);
    
    // 显示正在同步的提示
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('正在同步未上传的记录...'),
        duration: Duration(seconds: 1),
      ),
    );
    
    // 执行同步并获取结果
    final result = await notifier.syncUnuploadedRecords();
    
    if (!mounted) return;
    
    // 根据结果显示不同的提示
    String message;
    Color backgroundColor;
    
    final total = result['total'] ?? 0;
    final success = result['success'] ?? 0;
    final failed = result['failed'] ?? 0;
    final errors = result['errors'] as List? ?? [];
    
    if (total == 0) {
      // 无待同步记录
      message = '✅ 已是最新，无需同步';
      backgroundColor = Colors.grey;
    } else if (failed == 0 && success > 0) {
      // 全部成功
      message = '🎉 全部同步成功 ($success/$total)';
      backgroundColor = Colors.green;
    } else if (success > 0 && failed > 0) {
      // 部分成功
      message = '⚠️ 部分成功 ($success/$total)，$failed 个失败';
      backgroundColor = Colors.orange;
    } else if (failed > 0) {
      // 全部失败
      message = '❌ 同步失败 - ';
      
      // 追加具体的错误原因
      if (errors.isNotEmpty) {
        final firstError = errors.first.toString();
        if (firstError.contains('认证失败')) {
          message += '认证失败，请重新登录';
        } else if (firstError.contains('网络')) {
          message += '网络连接失败';
        } else if (firstError.contains('404')) {
          message += 'API端点不存在';
        } else if (firstError.contains('SSL')) {
          message += '证书问题';
        } else if (firstError.contains('文件不存在')) {
          message += '照片文件丢失';
        } else {
          message += '请检查网络';
        }
      } else {
        message += '请检查网络';
      }
      
      backgroundColor = Colors.red;
    } else {
      message = '同步完成';
      backgroundColor = Colors.blue;
    }
    
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: backgroundColor,
        duration: Duration(seconds: 4),
        action: failed > 0 && errors.isNotEmpty
            ? SnackBarAction(
                label: '查看详情',
                onPressed: () {
                  // 弹出详细的错误对话框
                  showDialog(
                    context: context,
                    builder: (context) => AlertDialog(
                      title: const Text('同步失败详情'),
                      content: SingleChildScrollView(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '成功: $success/$total',
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                color: Colors.green,
                              ),
                            ),
                            const SizedBox(height: 12),
                            if (errors.isNotEmpty) ...[
                              const Text(
                                '错误列表:',
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: Colors.red,
                                ),
                              ),
                              const SizedBox(height: 8),
                              ...errors
                                  .map((e) => Padding(
                                        padding:
                                            const EdgeInsets.only(bottom: 8),
                                        child: Text(
                                          '• $e',
                                          style: const TextStyle(fontSize: 12),
                                        ),
                                      ))
                                  .toList(),
                            ],
                          ],
                        ),
                      ),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text('关闭'),
                        ),
                      ],
                    ),
                  );
                },
              )
            : null,
      ),
    );
    
    // 刷新列表显示最新状态
    await notifier.loadFromLocal();
  }

  @override
  Widget build(BuildContext context) {
    final inspectionState = ref.watch(myInspectionsProvider);
    final unuploadedCount = ref.watch(unuploadedInspectionsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('巡查历史'),
        elevation: 2,
        actions: [
          if (unuploadedCount.hasValue && unuploadedCount.value!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.all(8.0),
              child: Center(
                child: ElevatedButton.icon(
                  onPressed: _syncRecords,
                  icon: const Icon(Icons.cloud_upload, size: 16),
                  label: Text('同步(${unuploadedCount.value!.length})'),
                ),
              ),
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadInspections,
        child: inspectionState.isLoading
            ? const Center(child: CircularProgressIndicator())
            : inspectionState.records.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.history,
                          size: 48,
                          color: Colors.grey[400],
                        ),
                        const SizedBox(height: 16),
                        Text(
                          '暂无巡查记录',
                          style: TextStyle(
                            fontSize: 16,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    itemCount: inspectionState.records.length,
                    itemBuilder: (context, index) {
                      final record = inspectionState.records[index];
                      return InspectionHistoryCard(record: record);
                    },
                  ),
      ),
    );
  }
}

/// 巡查历史卡片
class InspectionHistoryCard extends StatelessWidget {
  final InspectionRecord record;

  const InspectionHistoryCard({
    Key? key,
    required this.record,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final dateStr = DateFormat('yyyy-MM-dd HH:mm').format(record.inspectTime);
    
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: ExpansionTile(
        leading: CircleAvatar(
          backgroundColor: record.isNormal ? Colors.green[100] : Colors.red[100],
          child: Icon(
            record.isNormal ? Icons.check : Icons.warning,
            color: record.isNormal ? Colors.green : Colors.red,
          ),
        ),
        title: Text(
          record.siteName,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Text(
          dateStr,
          style: TextStyle(fontSize: 12, color: Colors.grey[600]),
        ),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('状态:'),
                    Chip(
                      label: Text(record.isNormal ? '正常' : '异常'),
                      backgroundColor:
                          record.isNormal ? Colors.green[100] : Colors.red[100],
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                if (record.issueDetails != null && record.issueDetails!.isNotEmpty)
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('问题描述:'),
                      const SizedBox(height: 4),
                      Text(
                        record.issueDetails!,
                        style: TextStyle(fontSize: 12, color: Colors.grey[700]),
                      ),
                      const SizedBox(height: 8),
                    ],
                  ),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('上传状态:'),
                    Chip(
                      label: Text(record.uploadedToServer ? '已上传' : '未上传'),
                      backgroundColor: record.uploadedToServer
                          ? Colors.blue[100]
                          : Colors.orange[100],
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                if (record.latitude != null && record.longitude != null)
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('位置信息:'),
                      Text(
                        '纬: ${record.latitude}, 经: ${record.longitude}',
                        style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                      ),
                    ],
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
