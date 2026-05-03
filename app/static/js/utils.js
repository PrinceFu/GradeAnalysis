/**
 * 成绩分析系统 - 通用工具函数
 */

// ECharts 统一色板
const COLORS = ['#4A90D9','#67C23A','#E6A23C','#F56C6C','#909399','#b37feb','#36cfc9','#ff85c0','#ffc53d'];

/**
 * 通用 API 请求封装，自动处理错误并显示 toast
 */
async function apiFetch(url, options = {}) {
    try {
        const resp = await fetch(url, options);
        if (!resp.ok) {
            let errMsg = `请求失败 (${resp.status})`;
            try {
                const errData = await resp.json();
                errMsg = errData.detail || errData.message || errMsg;
            } catch (_) {}
            throw new Error(errMsg);
        }
        return await resp.json();
    } catch (e) {
        if (e.name === 'TypeError' && e.message.includes('fetch')) {
            showToast('网络错误，请检查连接', 'error');
        }
        throw e;
    }
}

/**
 * 显示 toast 通知
 * @param {string} message - 消息内容
 * @param {'success'|'error'|'warning'|'info'} type - 消息类型
 * @param {number} duration - 显示时长（毫秒）
 */
function showToast(message, type = 'success', duration = 3000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }

    const iconMap = {
        success: 'bi-check-circle-fill text-success',
        error: 'bi-x-circle-fill text-danger',
        warning: 'bi-exclamation-triangle-fill text-warning',
        info: 'bi-info-circle-fill text-primary'
    };

    const bgMap = {
        success: 'border-start border-success border-4',
        error: 'border-start border-danger border-4',
        warning: 'border-start border-warning border-4',
        info: 'border-start border-primary border-4'
    };

    const toastEl = document.createElement('div');
    toastEl.className = `toast show ${bgMap[type] || bgMap.info}`;
    toastEl.setAttribute('role', 'alert');
    toastEl.innerHTML = `
        <div class="toast-body d-flex align-items-center gap-2">
            <i class="bi ${iconMap[type] || iconMap.info}"></i>
            <span>${message}</span>
        </div>
    `;

    container.appendChild(toastEl);

    setTimeout(() => {
        toastEl.classList.remove('show');
        toastEl.classList.add('hide');
        setTimeout(() => toastEl.remove(), 300);
    }, duration);
}

/**
 * 确认删除对话框
 * @param {string} message - 确认消息
 * @returns {boolean} 用户是否确认
 */
function confirmDelete(message = '确定要删除吗？此操作不可撤销。') {
    return confirm(message);
}
