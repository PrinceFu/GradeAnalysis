/**
 * 通用工具函数
 */

// Toast 通知
function showToast(message, type = 'success') {
    const container = document.querySelector('.toast-container') || createToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0 show`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    container.appendChild(toast);
    if (type === 'success') {
        setTimeout(() => toast.remove(), 3000);
    }
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
}

// 统一 fetch 封装
async function apiFetch(url, options = {}) {
    try {
        const resp = await fetch(url, options);
        if (resp.redirected) {
            window.location.href = resp.url;
            return null;
        }
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: '请求失败' }));
            showToast(err.detail || '请求失败', 'danger');
            throw new Error(err.detail);
        }
        return await resp.json();
    } catch (e) {
        if (!e.message || e.message === 'Failed to fetch') {
            showToast('网络错误，请检查连接', 'danger');
        }
        throw e;
    }
}

// 确认对话框
function confirmDelete(message = '确定要删除吗？此操作不可撤销。') {
    return new Promise(resolve => {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-sm modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-body text-center py-4">
                        <i class="bi bi-exclamation-triangle text-warning" style="font-size:48px;"></i>
                        <p class="mt-3 mb-0">${message}</p>
                    </div>
                    <div class="modal-footer justify-content-center">
                        <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-danger btn-sm" id="confirmBtn">确认删除</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        modal.querySelector('#confirmBtn').onclick = () => { bsModal.hide(); resolve(true); };
        modal.addEventListener('hidden.bs.modal', () => { modal.remove(); resolve(false); });
    });
}

// 分数格式化
function formatScore(score) {
    if (score === null || score === undefined) return '-';
    return Number(score).toFixed(1);
}

// 百分比格式化
function formatPercent(value) {
    return Number(value).toFixed(1) + '%';
}
