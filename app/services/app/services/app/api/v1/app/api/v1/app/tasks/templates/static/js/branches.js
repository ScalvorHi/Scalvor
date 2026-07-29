/**
 * Управление ветками на дашборде.
 * Создание, редактирование, drag-and-drop дерева веток.
 */

class BranchManager {
    constructor() {
        this.apiBase = '/api/v1/branches';
        this.currentProjectId = null;
        this.branches = [];
        this.treeContainer = document.getElementById('branchTree');
    }

    async loadBranches(projectId) {
        this.currentProjectId = projectId;
        try {
            const response = await fetch(`${this.apiBase}/project/${projectId}`, {
                headers: this.getHeaders(),
            });
            const data = await response.json();
            this.branches = data.branches;
            this.renderTree();
        } catch (error) {
            console.error('Ошибка загрузки веток:', error);
        }
    }

    getHeaders() {
        const token = localStorage.getItem('access_token');
        return {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        };
    }

    renderTree() {
        if (!this.treeContainer) return;

        this.treeContainer.innerHTML = '';
        this.branches.forEach(branch => {
            this.treeContainer.appendChild(this.createBranchNode(branch, 0));
        });
    }

    createBranchNode(branch, depth) {
        const node = document.createElement('div');
        node.className = 'tree-node';
        node.style.marginLeft = `${depth * 24}px`;
        node.setAttribute('data-branch-id', branch.id);
        node.setAttribute('draggable', 'true');

        node.innerHTML = `
            <div class="tree-node-header" style="border-left: 3px solid ${branch.color || '#ff69b4'}">
                <span class="tree-toggle">${branch.children && branch.children.length > 0 ? '&#9660;' : '&#9679;'}</span>
                <span class="tree-name">${this.escapeHtml(branch.name)}</span>
                <span class="tree-badge">${branch.notes_count || 0}</span>
                <span class="tree-actions">
                    <button class="tree-btn" onclick="branchManager.addNote('${branch.id}')" title="Добавить заметку">+</button>
                    <button class="tree-btn" onclick="branchManager.editBranch('${branch.id}')" title="Редактировать">&#9998;</button>
                    <button class="tree-btn" onclick="branchManager.deleteBranch('${branch.id}')" title="Удалить">&times;</button>
                </span>
            </div>
        `;

        // Обработчики drag-and-drop
        node.addEventListener('dragstart', (e) => this.onDragStart(e, branch.id));
        node.addEventListener('dragover', (e) => this.onDragOver(e));
        node.addEventListener('drop', (e) => this.onDrop(e, branch.id));
        node.addEventListener('dragleave', (e) => this.onDragLeave(e));

        // Рекурсивно добавляем дочерние ветки
        if (branch.children && branch.children.length > 0) {
            const childrenContainer = document.createElement('div');
            childrenContainer.className = 'tree-children';
            branch.children.forEach(child => {
                childrenContainer.appendChild(this.createBranchNode(child, depth + 1));
            });
            node.appendChild(childrenContainer);
        }

        return node;
    }

    async createBranch(name, parentId = null) {
        try {
            const response = await fetch(this.apiBase, {
                method: 'POST',
                headers: this.getHeaders(),
                body: JSON.stringify({
                    project_id: this.currentProjectId,
                    name: name,
                    parent_branch_id: parentId,
                }),
            });
            const data = await response.json();
            await this.loadBranches(this.currentProjectId);
            return data;
        } catch (error) {
            console.error('Ошибка создания ветки:', error);
        }
    }

    async editBranch(branchId) {
        const branch = this.findBranchById(branchId);
        if (!branch) return;

        const newName = prompt('Новое название ветки:', branch.name);
        if (!newName) return;

        try {
            await fetch(`${this.apiBase}/${branchId}`, {
                method: 'PATCH',
                headers: this.getHeaders(),
                body: JSON.stringify({ name: newName }),
            });
            await this.loadBranches(this.currentProjectId);
        } catch (error) {
            console.error('Ошибка обновления ветки:', error);
        }
    }

    async deleteBranch(branchId) {
        if (!confirm('Удалить ветку и всё содержимое?')) return;

        try {
            await fetch(`${this.apiBase}/${branchId}`, {
                method: 'DELETE',
                headers: this.getHeaders(),
            });
            await this.loadBranches(this.currentProjectId);
        } catch (error) {
            console.error('Ошибка удаления ветки:', error);
        }
    }

    async addNote(branchId) {
        const content = prompt('Текст заметки:');
        if (!content) return;

        try {
            await fetch(`${this.apiBase}/${branchId}/notes`, {
                method: 'POST',
                headers: this.getHeaders(),
                body: JSON.stringify({ content }),
            });
            await this.loadBranches(this.currentProjectId);
        } catch (error) {
            console.error('Ошибка добавления заметки:', error);
        }
    }

    async moveBranch(branchId, newParentId, orderIndex) {
        try {
            await fetch(`${this.apiBase}/${branchId}/move`, {
                method: 'PATCH',
                headers: this.getHeaders(),
                body: JSON.stringify({
                    new_parent_id: newParentId,
                    order_index: orderIndex,
                }),
            });
            await this.loadBranches(this.currentProjectId);
        } catch (error) {
            console.error('Ошибка перемещения ветки:', error);
        }
    }

    findBranchById(id) {
        const search = (branches) => {
            for (const b of branches) {
                if (b.id === id) return b;
                if (b.children) {
                    const found = search(b.children);
                    if (found) return found;
                }
            }
            return null;
        };
        return search(this.branches);
    }

    onDragStart(e, branchId) {
        e.dataTransfer.setData('text/plain', branchId);
        e.target.classList.add('dragging');
    }

    onDragOver(e) {
        e.preventDefault();
        e.target.closest('.tree-node')?.classList.add('drag-over');
    }

    onDragLeave(e) {
        e.target.closest('.tree-node')?.classList.remove('drag-over');
    }

    async onDrop(e, targetBranchId) {
        e.preventDefault();
        e.target.closest('.tree-node')?.classList.remove('drag-over');
        document.querySelector('.dragging')?.classList.remove('dragging');

        const draggedId = e.dataTransfer.getData('text/plain');
        if (draggedId === targetBranchId) return;

        await this.moveBranch(draggedId, targetBranchId, 0);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Глобальный экземпляр
const branchManager = new BranchManager();

// Загрузка при старте
document.addEventListener('DOMContentLoaded', () => {
    const projectSelect = document.getElementById('projectSelect');
    if (projectSelect) {
        projectSelect.addEventListener('change', (e) => {
            branchManager.loadBranches(e.target.value);
        });
    }
});

// Функции для кнопок быстрых действий
function newScan() {
    window.location.href = '/scans/new';
}

function newProject() {
    window.location.href = '/projects/new';
}

function quickDork() {
    window.location.href = '/tools/dorking';
}

function checkBreach() {
    window.location.href = '/tools/breach';
              }
