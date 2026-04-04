# 和风天气 API 接入技术文档

## 1. 概述

### 1.1 目标

接入和风天气（QWeather）API，为 Wanny 主动关怀系统提供准确的实时天气数据，触发温度变化关怀建议。

### 1.2 现有架构

当前天气服务位于 `backend/apps/care/services/weather.py`，通过 `ExternalDataSource` 模型管理数据源配置，支持：
- Open-Meteo API（默认免费方案）
- Home Assistant Entity（本地天气传感器）

新增和风天气作为第三种数据源类型。

---

## 2. 和风天气 API 规格

### 2.1 API 端点

| 功能 | 端点 | 说明 |
|------|------|------|
| 实时天气 | `GET /v7/weather/now` | 当前温度、天气状况 |
| 3天预报 | `GET /v7/weather/3d` | 未来3天预报 |
| 城市搜索 | `GET /v7/city/lookup` | 获取城市 Location ID |

**Base URL**:
- 免费订阅: `https://devapi.qweather.com` (低延迟，有限配额)
- 标准订阅: `https://api.qweather.com` (高可用，更大配额)

### 2.2 认证方式

```
?key={API_KEY}
```

API Key 通过 URL 参数传递，需要在和风天气控制台申请。

### 2.3 Location 参数

支持两种格式：

| 格式 | 示例 | 说明 |
|------|------|------|
| 城市 ID | `101010100` | 推荐，精准匹配 |
| 经纬度 | `116.41,39.92` | 格式 `经度,纬度` |

**城市 ID 获取方式**:
1. 通过城市搜索 API: `/v7/city/lookup?location={城市名}&key={key}`
2. 参考[城市列表](https://github.com/qwd/LocationList)

### 2.4 实时天气返回结构

```json
{
  "code": "200",
  "now": {
    "temp": "22",
    "text": "晴",
    "icon": "100",
    "windDir": "北",
    "windScale": "3",
    "windSpeed": "15",
    "humidity": "45",
    "pressure": "1013",
    "vis": "10",
    "cloud": "10"
  },
  "updateTime": "2024-01-15T10:00+08:00",
  "fxLink": "https://www.qweather.com/weather/beijing.html"
}
```

**关键字段映射**:

| 字段 | 含义 | 类型 |
|------|------|------|
| `now.temp` | 实时温度（摄氏度） | string |
| `now.text` | 天气状况文字 | string |
| `now.icon` | 天气图标代码 | string |
| `now.humidity` | 相对湿度（%） | string |
| `now.pressure` | 大气压强（hPa） | string |

### 2.5 错误响应

```json
{
  "code": "400",  // 错误码
  "message": "请求参数错误"
}
```

**常见错误码**:

| Code | 说明 |
|------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | API Key 无效 |
| 402 | 超过订阅配额 |
| 403 | 无访问权限 |
| 404 | 数据不存在 |
| 429 | 请求过于频繁 |

### 2.6 免费订阅限制

| 项目 | 限制 |
|------|------|
| 请求配额 | 1,000 次/天 |
| 请求频率 | 50 次/分钟 |
| 数据类型 | 实时天气、3天预报 |
| GZIP | 不支持 |

---

## 3. 数据模型设计

### 3.1 ExternalDataSource Config 结构

```python
{
    "provider": "qweather",
    "api_key": "YOUR_API_KEY",
    "location": "101010100",  # 城市 ID（推荐）
    # 或使用经纬度
    # "latitude": 39.92,
    # "longitude": 116.41,

    # 可选配置
    "endpoint": "https://devapi.qweather.com",  # 默认免费订阅
    "timeout_seconds": 8,
    "drop_threshold": 8.0,  # 温度下降阈值（触发关怀）
    "temperature_path": "now.temp",  # 温度字段路径
    "condition_path": "now.text",    # 天气状况字段路径
}
```

### 3.2 数据源类型扩展

`SourceTypeChoices` 已包含 `WEATHER_API`，无需新增类型，通过 `provider` 字段区分。

---

## 4. 代码实现方案

### 4.1 WeatherDataService 扩展

在 `_fetch_remote()` 方法中新增和风天气分支：

```python
@classmethod
def _fetch_remote(cls, *, source: ExternalDataSource, config: dict) -> dict:
    provider = config.get("provider", "")

    if provider == "qweather":
        return cls._fetch_qweather(config)

    # ... existing Open-Meteo / HA logic

@classmethod
def _fetch_qweather(cls, config: dict) -> dict:
    """Fetch weather data from QWeather API."""
    endpoint = str(config.get("endpoint") or "https://devapi.qweather.com").rstrip("/")
    api_key = str(config.get("api_key") or "").strip()
    if not api_key:
        raise ValueError("qweather provider requires api_key")

    # Location: prefer city_id, fallback to coordinates
    location = str(config.get("location") or "").strip()
    if not location:
        lat = config.get("latitude")
        lon = config.get("longitude")
        if lat is not None and lon is not None:
            location = f"{lon},{lat}"
        else:
            raise ValueError("qweather requires location (city_id) or latitude/longitude")

    timeout = max(int(config.get("timeout_seconds") or 8), 1)
    params = {
        "location": location,
        "key": api_key,
    }

    url = f"{endpoint}/v7/weather/now"
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "200":
        raise ValueError(f"QWeather API error: {data.get('code')} - {data.get('message', 'Unknown error')}")

    return data
```

### 4.2 字段提取适配

`_extract_temperature()` 和 `_extract_condition_text()` 已支持自定义路径，无需修改。

和风天气默认路径：
- 温度: `now.temp`
- 天气状况: `now.text`

在 `_normalize_payload()` 中添加和风天气识别：

```python
@classmethod
def _detect_provider(cls, config: dict) -> str:
    provider = str(config.get("provider") or "").strip().lower()
    if provider:
        return provider
    endpoint = str(config.get("endpoint") or "").lower()
    if "open-meteo" in endpoint:
        return "open_meteo"
    if "qweather" in endpoint:
        return "qweather"
    return "custom"

@classmethod
def _extract_temperature(cls, payload: dict, config: dict) -> float | None:
    # Support custom path first
    custom_path = str(config.get("temperature_path") or "").strip()
    if custom_path:
        return cls._to_float(cls._dig(payload, custom_path))

    # QWeather: now.temp
    if isinstance(payload.get("now"), dict):
        return cls._to_float(payload["now"].get("temp"))

    # ... existing Open-Meteo / HA logic
```

---

## 5. API 端点设计

### 5.1 创建和风天气数据源

**请求**:
```http
POST /care/data-sources
Content-Type: application/json
X-Wanny-Email: user@example.com

{
  "source_type": "weather_api",
  "name": "和风天气-上海",
  "config": {
    "provider": "qweather",
    "api_key": "YOUR_API_KEY",
    "location": "101020100"
  },
  "fetch_frequency": "30m",
  "is_active": true
}
```

**响应**:
```json
{
  "id": 1
}
```

### 5.2 验证规则

```python
def _validate_data_source(source_type: str, config: dict) -> tuple[bool, str]:
    if source_type == ExternalDataSource.SourceTypeChoices.WEATHER_API:
        provider = str(config.get("provider") or "").strip().lower()

        if provider == "qweather":
            if not str(config.get("api_key") or "").strip():
                return False, "qweather provider requires api_key"
            if not (str(config.get("location") or "").strip() or
                    (config.get("latitude") and config.get("longitude"))):
                return False, "qweather requires location (city_id) or latitude/longitude"
            return True, ""

        # ... existing Open-Meteo validation
```

---

## 6. 测试计划

### 6.1 单元测试

```python
# backend/tests/unit/test_weather_qweather.py

@pytest.mark.django_db
def test_fetch_qweather_with_city_id():
    """Test fetching weather data using city ID."""
    config = {
        "provider": "qweather",
        "api_key": "test_key",
        "location": "101010100",
        "endpoint": "https://devapi.qweather.com",
    }
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = {
            "code": "200",
            "now": {"temp": "25", "text": "晴"},
            "updateTime": "2024-01-15T10:00+08:00",
        }
        result = WeatherDataService._fetch_qweather(config)
        assert result["now"]["temp"] == "25"

@pytest.mark.django_db
def test_extract_temperature_from_qweather_payload():
    """Test temperature extraction from QWeather response."""
    payload = {"now": {"temp": "22", "text": "多云"}}
    result = WeatherDataService._extract_temperature(payload, {"provider": "qweather"})
    assert result == 22.0

@pytest.mark.django_db
def test_qweather_api_error_raises():
    """Test that QWeather API error code raises exception."""
    config = {"provider": "qweather", "api_key": "bad_key", "location": "101010100"}
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = {"code": "401", "message": "Invalid API key"}
        with pytest.raises(ValueError, match="QWeather API error"):
            WeatherDataService._fetch_qweather(config)
```

### 6.2 集成测试

```python
# backend/tests/integration/test_care_api.py (新增)

@pytest.mark.django_db
def test_create_qweather_data_source(client):
    account = Account.objects.create(email="qweather@example.com", name="qweather-test", password="x")
    response = client.post(
        reverse("care:data_sources"),
        data=json.dumps({
            "source_type": "weather_api",
            "name": "和风天气-北京",
            "config": {
                "provider": "qweather",
                "api_key": "test_api_key",
                "location": "101010100",
            },
            "fetch_frequency": "30m",
        }),
        content_type="application/json",
        HTTP_X_WANNY_EMAIL=account.email,
    )
    assert response.status_code == 201
    source = ExternalDataSource.objects.get(account=account)
    assert source.config["provider"] == "qweather"

@pytest.mark.django_db
def test_qweather_data_source_validation_requires_api_key(client):
    account = Account.objects.create(email="qweather-validation@example.com", name="test", password="x")
    response = client.post(
        reverse("care:data_sources"),
        data=json.dumps({
            "source_type": "weather_api",
            "name": "Missing Key",
            "config": {"provider": "qweather", "location": "101010100"},
        }),
        content_type="application/json",
        HTTP_X_WANNY_EMAIL=account.email,
    )
    assert response.status_code == 400
    assert "api_key" in response.json()["error"]
```

---

## 7. 实施步骤

### Phase 1: 核心实现（1天）

1. 扩展 `WeatherDataService._fetch_remote()` 支持和风天气
2. 新增 `_fetch_qweather()` 方法
3. 更新 `_extract_temperature()` 识别和风天气格式
4. 更新 `_detect_provider()` 返回 `qweather`

### Phase 2: 验证与 API（0.5天）

1. 更新 `_validate_data_source()` 验证和风天气配置
2. API 端点无需修改，通过 `config.provider` 区分

### Phase 3: 测试（0.5天）

1. 编写单元测试
2. 编写集成测试
3. 手动测试真实 API 调用

### Phase 4: 文档与部署（0.5天）

1. 更新用户文档
2. 部署验证
3. 监控配额使用

---

## 8. 配额管理建议

### 8.1 配额监控

建议在 `WeatherDataService.fetch_source()` 中记录请求次数：

```python
# Add to ProactiveLog or separate metric
ProactiveLog.objects.create(
    account=source.account,
    message=f"QWeather API request: {source.name}",
    feedback="API_CALL",
    source="qweather:quota",
)
```

### 8.2 缓存策略

- 默认 `fetch_frequency` 建议设置为 `30m`（每30分钟刷新）
- 免费配额 1,000 次/天 ≈ 每 1.44 分钟 1 次
- 30 分钟间隔下，每日最多 48 次请求（远低于配额）

### 8.3 错误降级

已有降级逻辑：API 失败时使用 `previous_data`，标记 `degraded: true`。

---

## 9. 安全考虑

1. **API Key 存储**: 存储在 `ExternalDataSource.config` JSON 字段，需确保：
   - 数据库访问权限控制
   - API 返回时不暴露完整 `api_key`（可掩码处理）

2. **请求限制**: 实现客户端级请求频率控制，避免触发 429 错误

3. **HTTPS**: 和风天气 API 强制 HTTPS，无需额外配置

---

## 10. 附录

### 10.1 常用城市 ID

| 城市 | Location ID |
|------|-------------|
| 北京 | 101010100 |
| 上海 | 101020100 |
| 广州 | 101280101 |
| 深圳 | 101280601 |
| 杭州 | 101210101 |
| 成都 | 101270101 |
| 武汉 | 101200101 |
| 南京 | 101190101 |

### 10.2 天气图标代码对照

| Icon | 天气 |
|------|------|
| 100 | 晴 |
| 101 | 多云 |
| 102 | 少云 |
| 103 | 晴间多云 |
| 104 | 阴 |
| 150 | 晴（夜间） |
| 151 | 多云（夜间） |
| 300-399 | 雨 |
| 400-499 | 雪 |
| 500-599 | 雾/霾 |
| 900 | 热 |
| 901 | 冷 |

### 10.3 参考链接

- [和风天气开发文档](https://dev.qweather.com/docs/api/)
- [实时天气 API](https://dev.qweather.com/docs/api/weather/weather-now/)
- [城市列表 JSON](https://github.com/qwd/LocationList)
- [API 状态码](https://dev.qweather.com/docs/resource/status-code/)