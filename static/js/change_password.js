/**
 * 用户自助修改密码 Modal 交互
 */
(function () {
    function getModal() {
        return document.getElementById('changePasswordModal');
    }

    function clearForm() {
        ['cpOldPassword', 'cpNewPassword', 'cpConfirmPassword'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) {
                el.value = '';
                el.type = 'password';
            }
        });
        var err = document.getElementById('cpErrorMsg');
        if (err) {
            err.textContent = '';
            err.style.display = 'none';
        }
    }

    window.openChangePasswordModal = function () {
        var modalEl = getModal();
        if (!modalEl) return;
        clearForm();
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    };

    window.toggleChangePasswordVisibility = function (inputId, btn) {
        var inp = document.getElementById(inputId);
        if (!inp) return;
        var icon = btn && btn.querySelector('i');
        if (inp.type === 'password') {
            inp.type = 'text';
            if (icon) {
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            }
        } else {
            inp.type = 'password';
            if (icon) {
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        }
    };

    window.submitChangePassword = async function () {
        var oldPassword = document.getElementById('cpOldPassword').value;
        var newPassword = document.getElementById('cpNewPassword').value;
        var confirmPassword = document.getElementById('cpConfirmPassword').value;
        var errEl = document.getElementById('cpErrorMsg');
        var btn = document.getElementById('cpSubmitBtn');

        errEl.style.display = 'none';
        errEl.textContent = '';

        if (!oldPassword) {
            errEl.textContent = '请输入当前密码';
            errEl.style.display = 'block';
            return;
        }
        if (!newPassword || newPassword.length < 4) {
            errEl.textContent = '新密码不能为空且至少4位';
            errEl.style.display = 'block';
            return;
        }
        if (newPassword !== confirmPassword) {
            errEl.textContent = '两次输入的新密码不一致';
            errEl.style.display = 'block';
            return;
        }

        btn.disabled = true;
        try {
            var res = await fetch('/api/auth/change-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    old_password: oldPassword,
                    new_password: newPassword,
                    confirm_password: confirmPassword
                })
            });
            var json = await res.json();
            if (json.success) {
                bootstrap.Modal.getInstance(getModal()).hide();
                alert(json.message || '密码已修改');
            } else {
                errEl.textContent = json.message || '修改失败';
                errEl.style.display = 'block';
            }
        } catch (e) {
            errEl.textContent = '网络错误，请稍后重试';
            errEl.style.display = 'block';
        } finally {
            btn.disabled = false;
        }
    };
})();
