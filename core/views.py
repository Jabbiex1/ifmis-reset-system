import os
import mimetypes
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import HttpResponse, Http404
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q

from .forms import IFMISResetForm, IFMISRequestMessageForm
from .models import IFMISResetRequest, IFMISRequestMessage, AuditLog


# ── Helpers ──────────────────────────────────────────────────────────────────

def is_ifmis_admin(user):
    return user.is_authenticated and user.groups.filter(name='IFMIS_ADMIN').exists()


def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def is_rate_limited(ip, limit=5, window=3600):
    cache_key = f'ifmis_submit_{ip}'
    count = cache.get(cache_key, 0)
    if count >= limit:
        return True
    cache.set(cache_key, count + 1, timeout=window)
    return False


def log_action(request, action, ref_code=None, detail=''):
    """Create an immutable AuditLog entry."""
    AuditLog(
        admin=request.user if request.user.is_authenticated else None,
        action=action,
        ref_code=ref_code,
        detail=detail,
        ip_address=get_client_ip(request),
    ).save()


# ── Email helpers ─────────────────────────────────────────────────────────────

def send_submission_email(req):
    try:
        send_mail(
            subject='IFMIS Help Desk — Your Password Reset Request Has Been Received',
            message=(
                f"Dear {req.full_name},\n\n"
                f"Your IFMIS password reset request has been received.\n\n"
                f"Your Reference Code: {req.reference_code}\n\n"
                f"Track your request at: {settings.SITE_URL}/track/?ref={req.reference_code}\n\n"
                f"— IFMIS Help Desk, DFMST, Ministry of Finance, Sierra Leone"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[req.email],
            fail_silently=True,
        )
    except Exception:
        pass


def send_processed_email(req):
    try:
        send_mail(
            subject='IFMIS Help Desk — Your Password Reset Request Has Been Processed',
            message=(
                f"Dear {req.full_name},\n\n"
                f"Your IFMIS password reset request (Ref: {req.reference_code}) "
                f"has been processed by the Help Desk.\n\n"
                f"If you have not received your new password, contact us at:\n"
                f"📧 ifmis.support@mof.gov.sl  |  📞 +232 31 399 020\n\n"
                f"— IFMIS Help Desk, DFMST, Ministry of Finance, Sierra Leone"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[req.email],
            fail_silently=True,
        )
    except Exception:
        pass


# ── Logout ────────────────────────────────────────────────────────────────────

def staff_logout(request):
    if request.method == 'POST':
        log_action(request, AuditLog.ACTION_LOGOUT)
        logout(request)
    return redirect('/staff/login/')


# ── PUBLIC: Submit Request ────────────────────────────────────────────────────

def upload_request(request):
    reference_code = None
    form = IFMISResetForm()
    rate_limited = False

    if request.method == 'POST':
        ip = get_client_ip(request)
        if is_rate_limited(ip):
            rate_limited = True
        else:
            form = IFMISResetForm(request.POST, request.FILES)
            if form.is_valid():
                new_request = form.save()
                reference_code = new_request.reference_code
                form = IFMISResetForm()
                send_submission_email(new_request)

    return render(request, 'upload.html', {
        'form': form,
        'reference_code': reference_code,
        'rate_limited': rate_limited,
    })


# ── PUBLIC: Track Request ─────────────────────────────────────────────────────

def track_request(request):
    request_obj = None
    chat_messages = []
    error = None
    form = None
    ref_code = request.GET.get('ref', '').strip().upper()

    if ref_code:
        try:
            request_obj = IFMISResetRequest.objects.get(reference_code=ref_code)
            chat_messages = request_obj.messages.all()
            form = IFMISRequestMessageForm()
        except IFMISResetRequest.DoesNotExist:
            error = f'No request found with reference code "{ref_code}". Please check and try again.'

    if request.method == 'POST':
        ref_code = request.POST.get('ref_code', '').strip().upper()
        try:
            request_obj = IFMISResetRequest.objects.get(reference_code=ref_code)
            form = IFMISRequestMessageForm(request.POST)
            if form.is_valid():
                msg = form.save(commit=False)
                msg.request = request_obj
                msg.sender = 'user'
                msg.save()
                return redirect(f'/track/?ref={ref_code}')
            chat_messages = request_obj.messages.all()
        except IFMISResetRequest.DoesNotExist:
            error = f'No request found with reference code "{ref_code}".'

    return render(request, 'track_request.html', {
        'request_obj': request_obj,
        'chat_messages': chat_messages,
        'form': form,
        'ref_code': ref_code,
        'error': error,
    })


# ── #2: Protected file serving ────────────────────────────────────────────────

import os
import mimetypes
from django.conf import settings
from django.http import Http404, HttpResponse

def serve_uploaded_file(request, filename):
    # Always load from media/uploads/
    file_path = os.path.join(settings.MEDIA_ROOT, "uploads", filename)

    if not os.path.exists(file_path):
        raise Http404("File not found.")

    # 🔐 Permission logic
    if not is_ifmis_admin(request.user):
        ref_code = request.GET.get('ref', '').strip().upper()
        if not ref_code:
            raise Http404("Access denied.")
        try:
            req = IFMISResetRequest.objects.get(reference_code=ref_code)
            if not req.uploaded_file or os.path.basename(req.uploaded_file.name) != filename:
                raise Http404("Access denied.")
        except IFMISResetRequest.DoesNotExist:
            raise Http404("Access denied.")

    # 📦 Serve file
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or 'application/octet-stream'

    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type=content_type)

    # 👀 or ⬇ switch
    if request.GET.get("download") == "1":
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    else:
        response['Content-Disposition'] = f'inline; filename="{filename}"'

    return response
# ── ADMIN: Dashboard ──────────────────────────────────────────────────────────

@login_required(login_url='/staff/login/')
@user_passes_test(is_ifmis_admin, login_url='/staff/login/')
def dashboard_requests(request):
    qs = IFMISResetRequest.objects.all().order_by('-submitted_at')

    search = request.GET.get('q', '').strip()
    day    = request.GET.get('day', '').strip()
    month  = request.GET.get('month', '').strip()
    year   = request.GET.get('year', '').strip()

    if search:
        qs = qs.filter(
            Q(full_name__icontains=search) |
            Q(department__icontains=search) |
            Q(email__icontains=search) |
            Q(reference_code__icontains=search)
        )
    if day.isdigit():
        qs = qs.filter(submitted_at__day=int(day))
    if month.isdigit():
        qs = qs.filter(submitted_at__month=int(month))
    if year.isdigit():
        qs = qs.filter(submitted_at__year=int(year))

    today = date.today()
    for req in qs:
        req.days_open = (today - req.submitted_at.date()).days

    paginator = Paginator(qs, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    filter_qs = query_params.urlencode()

    return render(request, 'staff/dashboard_requests.html', {
        'requests': page_obj,
        'page_obj': page_obj,
        'search': search,
        'day': day,
        'month': month,
        'year': year,
        'filter_qs': filter_qs,
        'total_count': IFMISResetRequest.objects.count(),
    })


# ── ADMIN: Delete single request ──────────────────────────────────────────────

@login_required(login_url='/staff/login/')
@user_passes_test(is_ifmis_admin, login_url='/staff/login/')
def delete_request(request, pk):
    req = get_object_or_404(IFMISResetRequest, pk=pk)
    if request.method == 'POST':
        ref = req.reference_code
        name = req.full_name
        log_action(
            request,
            AuditLog.ACTION_DELETE_REQUEST,
            ref_code=ref,
            detail=f"Deleted request from {name} ({req.email})"
        )
        req.uploaded_file.delete(save=False)  # remove file from disk
        req.delete()
        messages.success(request, f"Request {ref} ({name}) has been permanently deleted.")
        return redirect('dashboard_requests')
    # GET — show confirmation page
    return render(request, 'staff/confirm_delete.html', {'req': req})


# ── ADMIN: Bulk delete ────────────────────────────────────────────────────────

@login_required(login_url='/staff/login/')
@user_passes_test(is_ifmis_admin, login_url='/staff/login/')
def bulk_delete_requests(request):
    if request.method == 'POST':
        pks = request.POST.getlist('selected_ids')
        if not pks:
            messages.error(request, "No requests were selected.")
            return redirect('dashboard_requests')

        reqs = IFMISResetRequest.objects.filter(pk__in=pks)
        count = reqs.count()
        refs = ', '.join(r.reference_code for r in reqs)

        # Delete files from disk first
        for r in reqs:
            if r.uploaded_file:
                r.uploaded_file.delete(save=False)

        log_action(
            request,
            AuditLog.ACTION_BULK_DELETE,
            detail=f"Bulk deleted {count} request(s): {refs}"
        )
        reqs.delete()
        messages.success(request, f"{count} request(s) permanently deleted.")
    return redirect('dashboard_requests')


# ── ADMIN: Mark as Processed ──────────────────────────────────────────────────

@login_required(login_url='/staff/login/')
@user_passes_test(is_ifmis_admin, login_url='/staff/login/')
def process_request(request, pk):
    req = get_object_or_404(IFMISResetRequest, pk=pk)
    req.processed = True
    req.save()
    log_action(request, AuditLog.ACTION_MARK_PROCESSED, ref_code=req.reference_code,
               detail=f"Marked {req.full_name}'s request as processed")
    messages.success(request, f"{req.full_name}'s request has been marked as processed.")
    send_processed_email(req)
    return redirect('dashboard_requests')


# ── ADMIN: Request Detail ─────────────────────────────────────────────────────

@login_required(login_url='/staff/login/')
@user_passes_test(is_ifmis_admin, login_url='/staff/login/')
def admin_request_detail(request, ref_code):
    request_obj = get_object_or_404(IFMISResetRequest, reference_code=ref_code)
    form = IFMISRequestMessageForm()

    # Log view
    log_action(request, AuditLog.ACTION_VIEW_REQUEST, ref_code=ref_code,
               detail=f"Viewed request for {request_obj.full_name}")

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'reply':
            form = IFMISRequestMessageForm(request.POST)
            if form.is_valid():
                msg = form.save(commit=False)
                msg.request = request_obj
                msg.sender = 'admin'
                msg.save()
                log_action(request, AuditLog.ACTION_SEND_REPLY, ref_code=ref_code,
                           detail=f"Reply: {msg.content[:120]}")
                return redirect('admin_request_detail', ref_code=ref_code)

        elif action == 'mark_processed':
            request_obj.processed = True
            request_obj.save()
            log_action(request, AuditLog.ACTION_MARK_PROCESSED, ref_code=ref_code,
                       detail=f"Marked {request_obj.full_name}'s request as processed")
            messages.success(request, f"{request_obj.full_name}'s request marked as processed.")
            send_processed_email(request_obj)
            return redirect('dashboard_requests')

        elif action == 'mark_pending':
            request_obj.processed = False
            request_obj.save()
            log_action(request, AuditLog.ACTION_MARK_PENDING, ref_code=ref_code,
                       detail=f"Reverted {request_obj.full_name}'s request to pending")
            messages.success(request, f"{request_obj.full_name}'s request reverted to pending.")
            return redirect('admin_request_detail', ref_code=ref_code)

        elif action == 'delete':
            name = request_obj.full_name
            log_action(request, AuditLog.ACTION_DELETE_REQUEST, ref_code=ref_code,
                       detail=f"Deleted request from {name} ({request_obj.email})")
            if request_obj.uploaded_file:
                request_obj.uploaded_file.delete(save=False)
            request_obj.delete()
            messages.success(request, f"Request {ref_code} ({name}) permanently deleted.")
            return redirect('dashboard_requests')

    chat_messages = request_obj.messages.all()

    return render(request, 'staff/request_detail.html', {
        'request_obj': request_obj,
        'chat_messages': chat_messages,
        'form': form,
    })


# ── ADMIN: Audit Log ──────────────────────────────────────────────────────────

@login_required(login_url='/staff/login/')
@user_passes_test(is_ifmis_admin, login_url='/staff/login/')
def audit_log_view(request):
    qs = AuditLog.objects.select_related('admin').all()

    # Filters
    admin_filter  = request.GET.get('admin', '').strip()
    action_filter = request.GET.get('action', '').strip()
    ref_filter    = request.GET.get('ref', '').strip().upper()
    date_filter   = request.GET.get('date', '').strip()

    if admin_filter:
        qs = qs.filter(admin__username__icontains=admin_filter)
    if action_filter:
        qs = qs.filter(action=action_filter)
    if ref_filter:
        qs = qs.filter(ref_code__icontains=ref_filter)
    if date_filter:
        try:
            from datetime import datetime
            d = datetime.strptime(date_filter, '%Y-%m-%d').date()
            qs = qs.filter(timestamp__date=d)
        except ValueError:
            pass

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    query_params = request.GET.copy()
    query_params.pop('page', None)

    return render(request, 'staff/audit_log.html', {
        'logs': page_obj,
        'page_obj': page_obj,
        'action_choices': AuditLog.ACTION_CHOICES,
        'admin_filter': admin_filter,
        'action_filter': action_filter,
        'ref_filter': ref_filter,
        'date_filter': date_filter,
        'filter_qs': query_params.urlencode(),
        'total_count': AuditLog.objects.count(),
    })