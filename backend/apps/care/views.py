import json
from datetime import datetime

from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from care.models import CareSuggestion, ExternalDataSource, InspectionRule
from care.services.processor import CareEventProcessor
from care.services.push import CarePushService
from care.services.scanner import InspectionScanner
from care.services.weather import WeatherDataService
from care.services.workflow import CareWorkflowService


def _format_datetime(value) -> str | None:
    if not value:
        return None
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _serialize_push_audit(item: CareSuggestion) -> dict:
    now = timezone.now()
    feedback = item.user_feedback if isinstance(item.user_feedback, dict) else {}
    push_state = feedback.get("push") if isinstance(feedback.get("push"), dict) else {}
    last_pushed_at = None
    last_pushed_at_raw = push_state.get("last_pushed_at")
    if last_pushed_at_raw:
        try:
            parsed = datetime.fromisoformat(str(last_pushed_at_raw))
            last_pushed_at = parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
        except (ValueError, TypeError):
            last_pushed_at = None

    ignored_until = None
    action = str(feedback.get("action") or "").strip().lower()
    if action == "ignore" and item.feedback_collected_at:
        ignored_until = item.feedback_collected_at + CarePushService.default_ignore_gap

    repeat_eligible_at = None
    if last_pushed_at:
        repeat_eligible_at = last_pushed_at + CarePushService.default_repeat_gap

    push_level = CarePushService._push_level(float(item.priority or 0))
    suppress_reason = None
    if push_level == "low":
        suppress_reason = "console_only"
    elif ignored_until and now < ignored_until:
        suppress_reason = "ignored_cooldown"
    elif repeat_eligible_at and now < repeat_eligible_at:
        suppress_reason = "repeat_gap"

    return {
        "level": push_level,
        "pushCount": int(push_state.get("count") or 0),
        "lastPushedAt": _format_datetime(last_pushed_at),
        "repeatEligibleAt": _format_datetime(repeat_eligible_at),
        "ignoredUntil": _format_datetime(ignored_until),
        "consoleOnly": push_level == "low",
        "suppressReason": suppress_reason,
    }


def _serialize_aggregation_sources(item: CareSuggestion) -> list[dict]:
    markers = item.aggregated_from if isinstance(item.aggregated_from, list) else []
    numeric_markers = [marker for marker in markers if isinstance(marker, int) or (isinstance(marker, str) and str(marker).isdigit())]
    normalized_ids = [int(marker) for marker in numeric_markers]

    if item.suggestion_type == CareSuggestion.SuggestionTypeChoices.INSPECTION:
        rule_map = {
            rule.id: rule
            for rule in InspectionRule.objects.filter(id__in=normalized_ids).only("id", "name", "rule_type")
        }
        sources = []
        for marker in markers:
            marker_id = int(marker) if isinstance(marker, str) and str(marker).isdigit() else marker
            rule = rule_map.get(marker_id) if isinstance(marker_id, int) else None
            if rule:
                sources.append(
                    {
                        "kind": "rule",
                        "id": rule.id,
                        "label": rule.name,
                        "detail": rule.get_rule_type_display(),
                    }
                )
            else:
                sources.append(
                    {
                        "kind": "rule",
                        "id": marker if isinstance(marker, int) else None,
                        "label": f"Rule #{marker}",
                        "detail": "",
                    }
                )
        return sources

    source_map = {
        source.id: source
        for source in ExternalDataSource.objects.filter(id__in=normalized_ids).only("id", "name", "source_type")
    }
    event_name = ""
    if isinstance(item.source_event, dict):
        event_name = str(item.source_event.get("event") or "").strip()
    event_labels = {
        "weather_temperature_drop": "Temperature drop",
    }
    sources = []
    for marker in markers:
        marker_id = int(marker) if isinstance(marker, str) and str(marker).isdigit() else marker
        source = source_map.get(marker_id) if isinstance(marker_id, int) else None
        if source:
            sources.append(
                {
                    "kind": "data_source",
                    "id": source.id,
                    "label": source.name,
                    "detail": source.get_source_type_display(),
                }
            )
        else:
            sources.append(
                {
                    "kind": "data_source",
                    "id": marker if isinstance(marker, int) else None,
                    "label": f"Source #{marker}",
                    "detail": "",
                }
            )
    if event_name:
        sources.append(
            {
                "kind": "event",
                "id": None,
                "label": event_labels.get(event_name, event_name.replace("_", " ")),
                "detail": "Event",
            }
        )
    return sources


def _serialize_suggestion(item: CareSuggestion) -> dict:
    return {
        "id": item.id,
        "suggestionType": item.suggestion_type,
        "title": item.title,
        "body": item.body,
        "priority": item.priority,
        "status": item.status,
        "aggregatedCount": item.aggregated_count,
        "aggregatedFrom": item.aggregated_from if isinstance(item.aggregated_from, list) else [],
        "aggregationSources": _serialize_aggregation_sources(item),
        "device": {
            "id": item.device.external_id,
            "name": item.device.name,
            "category": item.device.category,
        } if item.device else None,
        "control": {
            "id": item.control_target.external_id,
            "key": item.control_target.key,
            "label": item.control_target.label,
        } if item.control_target else None,
        "actionSpec": item.action_spec or {},
        "missionId": item.mission_id,
        "createdAt": item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "updatedAt": item.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        "pushAudit": _serialize_push_audit(item),
        "canApprove": item.status == CareSuggestion.StatusChoices.PENDING,
        "canReject": item.status == CareSuggestion.StatusChoices.PENDING,
        "canIgnore": item.status == CareSuggestion.StatusChoices.PENDING,
        "canExecute": bool(item.action_spec.get("control_id") or item.control_target_id),
    }


def _serialize_rule(rule: InspectionRule) -> dict:
    return {
        "id": rule.id,
        "ruleType": rule.rule_type,
        "deviceCategory": rule.device_category,
        "name": rule.name,
        "description": rule.description,
        "checkFrequency": rule.check_frequency,
        "conditionSpec": rule.condition_spec,
        "actionSpec": rule.action_spec,
        "suggestionTemplate": rule.suggestion_template,
        "priority": rule.priority,
        "cooldownHours": rule.cooldown_hours,
        "isSystemDefault": rule.is_system_default,
        "isActive": rule.is_active,
    }


def _get_account(request):
    return getattr(request, "account", None)


def _priority_bucket(value: float) -> str:
    if value >= 7:
        return "high"
    if value >= 4:
        return "medium"
    return "low"


def _validate_condition_spec(condition_spec: dict) -> tuple[bool, str]:
    if not isinstance(condition_spec, dict):
        return False, "condition_spec must be an object"
    field = str(condition_spec.get("field") or "").strip()
    operator = str(condition_spec.get("operator") or "").strip().lower()
    if not field:
        return False, "condition_spec.field is required"
    if operator not in InspectionScanner.operator_map:
        return False, "condition_spec.operator is invalid"
    if operator != "exists" and "threshold" not in condition_spec:
        return False, "condition_spec.threshold is required"
    return True, ""


def _validate_data_source(source_type: str, config: dict) -> tuple[bool, str]:
    if source_type == ExternalDataSource.SourceTypeChoices.WEATHER_API:
        provider = str(config.get("provider") or "").strip().lower()
        if provider == "qweather":
            has_coords = config.get("latitude") is not None and config.get("longitude") is not None
            has_location = bool(str(config.get("location") or "").strip())
            if not (has_location or has_coords):
                return False, "qweather source requires location or latitude/longitude"
            return True, ""
        has_coords = config.get("latitude") is not None and config.get("longitude") is not None
        has_endpoint = bool(str(config.get("endpoint") or "").strip())
        if not (has_coords or has_endpoint):
            return False, "weather_api source requires endpoint or latitude/longitude"
        return True, ""
    if source_type == ExternalDataSource.SourceTypeChoices.HA_ENTITY:
        if not str(config.get("ha_entity_id") or config.get("entity_id") or "").strip():
            return False, "ha_entity source requires ha_entity_id"
        return True, ""
    return True, ""


@csrf_exempt
def handle_suggestions(request):
    if request.method == "GET":
        account = _get_account(request)
        if not account:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        queryset = CareSuggestion.objects.filter(account=account).select_related("device", "control_target", "mission", "source_rule")
        status = request.GET.get("status", "").strip()
        suggestion_type = request.GET.get("suggestion_type", "").strip()
        priority = request.GET.get("priority", "").strip()
        if status:
            queryset = queryset.filter(status=status)
        if suggestion_type:
            queryset = queryset.filter(suggestion_type=suggestion_type)
        if priority:
            queryset = [item for item in queryset if _priority_bucket(item.priority) == priority]
        else:
            queryset = list(queryset)
        return JsonResponse({"suggestions": [_serialize_suggestion(item) for item in queryset]}, status=200)
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def handle_suggestion_feedback(request, pk: int):
    if request.method != "POST":
        return JsonResponse({"error": "Method must be POST"}, status=405)
    account = _get_account(request)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    suggestion = CareSuggestion.objects.filter(account=account, pk=pk).select_related("device", "control_target").first()
    if suggestion is None:
        return JsonResponse({"error": "Suggestion not found"}, status=404)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    action = str(payload.get("action") or "").strip().lower()
    reason = str(payload.get("reason") or "").strip()
    if action == "approve":
        mission = CareWorkflowService.create_mission_for_suggestion(suggestion)
        return JsonResponse({"status": "approved", "missionId": mission.id, "suggestion": _serialize_suggestion(suggestion)}, status=200)
    if action == "reject":
        CareWorkflowService.reject_suggestion(suggestion, reason=reason)
        return JsonResponse({"status": "rejected", "suggestion": _serialize_suggestion(suggestion)}, status=200)
    if action == "ignore":
        CareWorkflowService.ignore_suggestion(suggestion, reason=reason)
        return JsonResponse({"status": "ignored", "suggestion": _serialize_suggestion(suggestion)}, status=200)
    return JsonResponse({"error": "Unsupported action"}, status=400)


@csrf_exempt
def handle_suggestion_confirm_detail(request, pk: int):
    if request.method != "GET":
        return JsonResponse({"error": "Method must be GET"}, status=405)
    account = _get_account(request)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    suggestion = CareSuggestion.objects.filter(account=account, pk=pk).select_related("device", "control_target", "mission").first()
    if suggestion is None:
        return JsonResponse({"error": "Suggestion not found"}, status=404)
    action_spec = suggestion.action_spec or {}
    return JsonResponse(
        {
            "suggestion": _serialize_suggestion(suggestion),
            "confirmDetail": {
                "deviceId": action_spec.get("device_id") or (suggestion.device.external_id if suggestion.device else ""),
                "deviceName": suggestion.device.name if suggestion.device else "",
                "controlId": action_spec.get("control_id") or (suggestion.control_target.external_id if suggestion.control_target else ""),
                "controlLabel": suggestion.control_target.label if suggestion.control_target else "",
                "action": action_spec.get("action", ""),
                "value": action_spec.get("value"),
                "missionId": suggestion.mission_id,
            },
        },
        status=200,
    )


@csrf_exempt
def handle_suggestion_execute(request, pk: int):
    if request.method != "POST":
        return JsonResponse({"error": "Method must be POST"}, status=405)
    account = _get_account(request)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    suggestion = CareSuggestion.objects.filter(account=account, pk=pk).select_related("device", "control_target", "mission").first()
    if suggestion is None:
        return JsonResponse({"error": "Suggestion not found"}, status=404)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    if payload.get("confirmed") is not True:
        return JsonResponse({"error": "confirmed must be true"}, status=400)
    try:
        result = CareWorkflowService.execute_suggestion(suggestion)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse({"status": suggestion.status, "result": result, "suggestion": _serialize_suggestion(suggestion)}, status=200)


@csrf_exempt
def handle_rules(request):
    account = _get_account(request)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if request.method == "GET":
        rules = InspectionRule.objects.filter(Q(account=account) | Q(account__isnull=True)).order_by("-is_system_default", "id")
        return JsonResponse({"rules": [_serialize_rule(rule) for rule in rules]}, status=200)
    if request.method == "POST":
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)
        is_valid, error_message = _validate_condition_spec(payload.get("condition_spec"))
        if not is_valid:
            return JsonResponse({"error": error_message}, status=400)
        rule = InspectionRule.objects.create(
            account=account,
            rule_type=str(payload.get("rule_type") or InspectionRule.RuleTypeChoices.CUSTOM),
            device_category=str(payload.get("device_category") or ""),
            name=str(payload.get("name") or "").strip(),
            description=str(payload.get("description") or "").strip(),
            check_frequency=str(payload.get("check_frequency") or "hourly"),
            condition_spec=payload.get("condition_spec") if isinstance(payload.get("condition_spec"), dict) else {},
            action_spec=payload.get("action_spec") if isinstance(payload.get("action_spec"), dict) else {},
            suggestion_template=str(payload.get("suggestion_template") or "{device_name} 需要关注"),
            priority=int(payload.get("priority") or 5),
            cooldown_hours=int(payload.get("cooldown_hours") or 24),
            is_system_default=False,
            is_active=bool(payload.get("is_active", True)),
        )
        return JsonResponse({"rule": _serialize_rule(rule)}, status=201)
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def handle_rule_detail(request, pk: int):
    account = _get_account(request)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    rule = InspectionRule.objects.filter(pk=pk, account=account).first()
    if rule is None:
        return JsonResponse({"error": "Rule not found"}, status=404)
    if request.method == "PUT":
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)
        next_condition_spec = payload.get("condition_spec", rule.condition_spec)
        if "condition_spec" in payload:
            is_valid, error_message = _validate_condition_spec(next_condition_spec)
            if not is_valid:
                return JsonResponse({"error": error_message}, status=400)
        for field in ("device_category", "name", "description", "check_frequency", "suggestion_template"):
            if field in payload:
                setattr(rule, field, str(payload.get(field) or ""))
        if "rule_type" in payload:
            rule.rule_type = str(payload.get("rule_type") or rule.rule_type)
        if "condition_spec" in payload and isinstance(payload.get("condition_spec"), dict):
            rule.condition_spec = payload["condition_spec"]
        if "action_spec" in payload and isinstance(payload.get("action_spec"), dict):
            rule.action_spec = payload["action_spec"]
        if "priority" in payload:
            rule.priority = int(payload.get("priority") or rule.priority)
        if "cooldown_hours" in payload:
            rule.cooldown_hours = int(payload.get("cooldown_hours") or rule.cooldown_hours)
        if "is_active" in payload:
            rule.is_active = bool(payload.get("is_active"))
        rule.save()
        return JsonResponse({"rule": _serialize_rule(rule)}, status=200)
    if request.method == "DELETE":
        if rule.is_system_default:
            return JsonResponse({"error": "System default rule cannot be deleted"}, status=400)
        rule.delete()
        return JsonResponse({"status": "deleted"}, status=200)
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def handle_data_sources(request):
    account = _get_account(request)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if request.method == "GET":
        sources = ExternalDataSource.objects.filter(account=account).order_by("id")
        return JsonResponse(
            {
                "dataSources": [
                    {
                        "id": item.id,
                        "sourceType": item.source_type,
                        "name": item.name,
                        "config": item.config,
                        "fetchFrequency": item.fetch_frequency,
                        "lastFetchAt": item.last_fetch_at.strftime("%Y-%m-%d %H:%M:%S") if item.last_fetch_at else None,
                        "lastData": item.last_data,
                        "isActive": item.is_active,
                    }
                    for item in sources
                ]
            },
            status=200,
        )
    if request.method == "POST":
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)
        source_type = str(payload.get("source_type") or ExternalDataSource.SourceTypeChoices.OTHER)
        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        is_valid, error_message = _validate_data_source(source_type, config)
        if not is_valid:
            return JsonResponse({"error": error_message}, status=400)
        item = ExternalDataSource.objects.create(
            account=account,
            source_type=source_type,
            name=str(payload.get("name") or "").strip(),
            config=config,
            fetch_frequency=str(payload.get("fetch_frequency") or "30m"),
            is_active=bool(payload.get("is_active", True)),
        )
        return JsonResponse({"id": item.id}, status=201)
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def handle_data_source_detail(request, pk: int):
    account = _get_account(request)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    source = ExternalDataSource.objects.filter(account=account, pk=pk).first()
    if source is None:
        return JsonResponse({"error": "Data source not found"}, status=404)
    if request.method == "PUT":
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)
        next_source_type = str(payload.get("source_type") or source.source_type)
        next_config = payload.get("config") if isinstance(payload.get("config"), dict) else source.config
        is_valid, error_message = _validate_data_source(next_source_type, next_config)
        if not is_valid:
            return JsonResponse({"error": error_message}, status=400)
        if "source_type" in payload:
            source.source_type = next_source_type
        if "name" in payload:
            source.name = str(payload.get("name") or source.name)
        if "config" in payload and isinstance(payload.get("config"), dict):
            source.config = payload["config"]
        if "fetch_frequency" in payload:
            source.fetch_frequency = str(payload.get("fetch_frequency") or source.fetch_frequency)
        if "is_active" in payload:
            source.is_active = bool(payload.get("is_active"))
        source.save()
        return JsonResponse({"status": "updated"}, status=200)
    if request.method == "DELETE":
        source.delete()
        return JsonResponse({"status": "deleted"}, status=200)
    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def handle_weather_current(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method must be GET"}, status=405)
    account = _get_account(request)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    source = ExternalDataSource.objects.filter(
        account=account,
        source_type__in=[
            ExternalDataSource.SourceTypeChoices.WEATHER_API,
            ExternalDataSource.SourceTypeChoices.HA_ENTITY,
        ],
        is_active=True,
    ).order_by("-updated_at").first()
    return JsonResponse({"weather": source.last_data if source else {}, "sourceId": source.id if source else None}, status=200)


@csrf_exempt
def handle_weather_refresh(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method must be POST"}, status=405)
    account = _get_account(request)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    source = ExternalDataSource.objects.filter(
        account=account,
        source_type__in=[
            ExternalDataSource.SourceTypeChoices.WEATHER_API,
            ExternalDataSource.SourceTypeChoices.HA_ENTITY,
        ],
        is_active=True,
    ).order_by("-updated_at").first()
    if source is None:
        return JsonResponse({"error": "Weather source not found"}, status=404)
    source = WeatherDataService.fetch_source(source)
    suggestion = CareEventProcessor.process_weather_source(source)
    return JsonResponse(
        {
            "weather": source.last_data,
            "sourceId": source.id,
            "suggestionId": suggestion.id if suggestion else None,
        },
        status=200,
    )


@csrf_exempt
def handle_run_inspection(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method must be POST"}, status=405)
    account = _get_account(request)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    created = InspectionScanner.scan_account(account)
    return JsonResponse({"created": [_serialize_suggestion(item) for item in created]}, status=200)


@csrf_exempt
def handle_geocode(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method must be GET"}, status=405)
    account = _get_account(request)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    longitude = request.GET.get("longitude", "").strip()
    latitude = request.GET.get("latitude", "").strip()
    if not longitude or not latitude:
        return JsonResponse({"error": "longitude and latitude are required"}, status=400)
    try:
        lon = float(longitude)
        lat = float(latitude)
    except ValueError:
        return JsonResponse({"error": "longitude and latitude must be numbers"}, status=400)
    try:
        result = WeatherDataService.reverse_geocode(lon, lat)
        return JsonResponse(result, status=200)
    except Exception as error:
        return JsonResponse({"error": str(error)}, status=500)
