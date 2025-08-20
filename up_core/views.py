import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from up_core.daemon import service, health_monitor, security_monitor

@require_GET
@login_required
def daemon_status(request):
    """Return the current status of the daemon as JSON"""
    status = service.daemon_status()
    
    # Add health and security issues if daemon is running
    if status['running']:
        try:
            status['health_issues'] = health_monitor.get_health_issues()
            status['security_issues'] = security_monitor.get_security_issues()
        except Exception as e:
            status['error'] = str(e)
    
    return JsonResponse(status)

@require_GET
@login_required
def system_health(request):
    """Return the current system health as JSON"""
    try:
        health_issues = health_monitor.check_health()
        return JsonResponse({
            'status': 'ok' if not health_issues else 'issues',
            'issues': health_issues,
            'count': len(health_issues)
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@require_GET
@login_required
def system_security(request):
    """Return the current system security status as JSON"""
    try:
        security_issues = security_monitor.check_security()
        return JsonResponse({
            'status': 'ok' if not security_issues else 'issues',
            'issues': security_issues,
            'count': len(security_issues)
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)