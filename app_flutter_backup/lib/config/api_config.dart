/// API 配置文件
class ApiConfig {
  // 后端服务基础地址
  static const String baseUrl = 'https://beichenhome.top:9081/api';
  
  // 天地图配置
  static const String tdtToken = '424ac2af85564078477428c1a2b72018';
  
  // 天地图图层URL (统一使用HTTPS协议，与后端保持一致)
  static const String tdtVecUrl = 'https://t{s}.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=$tdtToken';
  static const String tdtCvaUrl = 'https://t{s}.tianditu.gov.cn/cva_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cva&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=$tdtToken';
  static const String tdtImageUrl = 'https://t{s}.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=$tdtToken';
  static const String tdtCiaUrl = 'https://t{s}.tianditu.gov.cn/cia_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cia&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=$tdtToken';
  
  // API 端点
  static const String loginEndpoint = '/auth/login/';
  static const String userEndpoint = '/auth/user/';
  static const String nearbyHeritagesEndpoint = '/heritages/nearby/';
  static const String createInspectionEndpoint = '/inspections/';  // 标准REST: POST到此端点创建新记录
  static const String myInspectionsEndpoint = '/inspections/my-records/';
  static const String statisticsEndpoint = '/inspections/statistics/';
  
  // 网络超时设置（毫秒）
  static const int connectTimeout = 30000;
  static const int receiveTimeout = 30000;
  static const int sendTimeout = 30000;
  
  // Token 存储 key
  static const String tokenKey = 'auth_token';
  static const String userDataKey = 'user_data';
  
  // 定位服务配置
  static const int gpsAccuracy = 10; // 米
  static const int gpsRefreshInterval = 5000; // 毫秒
  
  // 拍照配置
  static const int maxPhotoSize = 5242880; // 5MB
  static const String photoQuality = 'high'; // 照片质量
}
