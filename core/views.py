from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import IFMISResetForm, IFMISRequestMessageForm
from .models import IFMISResetRequest, IFMISRequestMessage


# ── Helper ──────────────────────────────────────────────
def is_ifmis_admin(user):
    return user.is_authenticated and user.groups.filter(name="IFMIS_ADMIN").exists()


# ── PUBLIC: Submit Request ───────────────────────────────
def upload_request(request):
    """
    Public form. On success, stays on the same page and shows
    the reference code. User must manually go to /track/ themselves.
    """
    reference_code = None
    form = IFMISResetForm()

    if request.method == 'POST':
        form = IFMISResetForm(request.POST, request.FILES)
        if form.is_valid():
            new_request = form.save()
            reference_code = new_request.reference_code
            form = IFMISResetForm()  # reset form to blank after success

    return render(request, 'upload.html', {
        'form': form,
        'reference_code': reference_code,
    })


# ── PUBLIC: Track Request + User Chat ───────────────────
def track_request(request):
    """
    User enters their reference code to find their request.
    Once found, they can see status and send messages to admin.
    """
    request_obj = None
    chat_messages = []
    error = None
    form = None
    ref_code = request.GET.get('ref', '').strip().upper()

    # If ref_code in URL, look up the request
    if ref_code:
        try:
            request_obj = IFMISResetRequest.objects.get(reference_code=ref_code)
            chat_messages = request_obj.messages.all()
            form = IFMISRequestMessageForm()
        except IFMISResetRequest.DoesNotExist:
            error = f'No request found with reference code "{ref_code}". Please check and try again.'

    # Handle user sending a message
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


# ── ADMIN: Dashboard ─────────────────────────────────────
@login_required(login_url='/staff/login/')
@user_passes_test(is_ifmis_admin, login_url='/staff/login/')
def dashboard_requests(request):
    requests_list = IFMISResetRequest.objects.all().order_by('-submitted_at')
    return render(request, 'staff/dashboard_requests.html', {
        'requests': requests_list,
    })

from django.contrib.auth import logout

def staff_logout(request):
    logout(request)
    return redirect('/staff/login/')

# ── ADMIN: Mark as Processed ─────────────────────────────
@login_required(login_url='/staff/login/')
@user_passes_test(is_ifmis_admin, login_url='/staff/login/')
def process_request(request, pk):
    req = get_object_or_404(IFMISResetRequest, pk=pk)
    req.processed = True
    req.save()
    messages.success(request, f"{req.full_name}'s request has been marked as processed.")
    return redirect('dashboard_requests')


# ── ADMIN: Request Detail + Admin Chat ───────────────────
@login_required(login_url='/staff/login/')
@user_passes_test(is_ifmis_admin, login_url='/staff/login/')
def admin_request_detail(request, ref_code):
    request_obj = get_object_or_404(IFMISResetRequest, reference_code=ref_code)
    form = IFMISRequestMessageForm()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'reply':
            form = IFMISRequestMessageForm(request.POST)
            if form.is_valid():
                msg = form.save(commit=False)
                msg.request = request_obj
                msg.sender = 'admin'
                msg.save()
                return redirect('admin_request_detail', ref_code=ref_code)

        elif action == 'mark_processed':
            request_obj.processed = True
            request_obj.save()
            messages.success(request, f"{request_obj.full_name}'s request marked as processed.")
            return redirect('dashboard_requests')

        elif action == 'mark_pending':
            request_obj.processed = False
            request_obj.save()
            messages.success(request, f"{request_obj.full_name}'s request reverted to pending.")
            return redirect('admin_request_detail', ref_code=ref_code)

    chat_messages = request_obj.messages.all()

    return render(request, 'staff/request_detail.html', {
        'request_obj': request_obj,
        'chat_messages': chat_messages,
        'form': form,
    })