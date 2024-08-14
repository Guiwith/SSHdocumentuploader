import os
import time
import threading
import webbrowser
from flask import Flask, request, render_template, redirect, url_for
import paramiko

app = Flask(__name__)

# 配置云服务器连接信息
HOST = 'YOURIP'
USERNAME = 'USERNAME'
PASSWORD = 'PASSWORD'
ENABLED_PATH = 'ENABLED_PATH'
DISABLED_PATH = 'DISABLED_PATH'

# 确保 UnloadedDatabase 文件夹存在
if not os.path.exists(DISABLED_PATH):
    os.makedirs(DISABLED_PATH)

# 连接到云服务器
def connect_to_server():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USERNAME, password=PASSWORD)
    return ssh

# 定义 datetimeformat 过滤器
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    if value is None:
        return "N/A"
    return time.strftime(format, time.localtime(value))

# 获取文件列表及其信息
def get_files(sftp, search_query=None):
    files = []

    def add_files_from_directory(directory, enabled):
        all_files = sftp.listdir(directory)
        if search_query:
            all_files = [f for f in all_files if search_query.lower() in f.lower()]

        for filename in all_files:
            file_path = os.path.join(directory, filename)
            stat = sftp.stat(file_path)
            files.append({
                'name': filename,
                'size': stat.st_size,
                'updated': stat.st_mtime,
                'enabled': enabled
            })

    add_files_from_directory(ENABLED_PATH, True)  # 添加启用状态的文件
    add_files_from_directory(DISABLED_PATH, False)  # 添加未启用状态的文件

    return files

# 主页
@app.route('/')
def index():
    search_query = request.args.get('search')
    page = int(request.args.get('page', 1))
    ssh = connect_to_server()
    sftp = ssh.open_sftp()
    files = get_files(sftp, search_query)
    total_files = len(files)
    files = files[(page-1)*10:page*10]  # 实现分页
    sftp.close()
    ssh.close()
    return render_template('index.html', files=files, page=page, total_files=total_files, search_query=search_query)

# 切换启用状态
@app.route('/toggle_enable/<filename>')
def toggle_enable(filename):
    ssh = connect_to_server()
    sftp = ssh.open_sftp()

    enabled_file_path = os.path.join(ENABLED_PATH, filename)
    disabled_file_path = os.path.join(DISABLED_PATH, filename)

    try:
        if file_exists(sftp, enabled_file_path):
            # 文件已启用，禁用它：移动到 UnloadedDatabase 文件夹
            sftp.rename(enabled_file_path, disabled_file_path)
        elif file_exists(sftp, disabled_file_path):
            # 文件已禁用，启用它：移动到 DOCDatabase 文件夹
            sftp.rename(disabled_file_path, enabled_file_path)
        else:
            print(f"Error: {filename} not found in either directory.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sftp.close()
        ssh.close()

    return redirect(url_for('index'))

def file_exists(sftp, path):
    """检查文件是否存在"""
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False

# 编辑文件
@app.route('/edit/<filename>', methods=['GET', 'POST'])
def edit_file(filename):
    ssh = connect_to_server()
    sftp = ssh.open_sftp()

    # 确定文件所在路径
    file_path = os.path.join(ENABLED_PATH, filename)
    if not file_exists(sftp, file_path):
        file_path = os.path.join(DISABLED_PATH, filename)
    
    if request.method == 'POST':
        content = request.form['content']
        with sftp.open(file_path, 'w') as f:
            f.write(content)
        sftp.close()
        ssh.close()
        return redirect(url_for('index'))
    
    with sftp.open(file_path, 'r') as f:
        content = f.read().decode('utf-8')
    
    sftp.close()
    ssh.close()
    return render_template('edit.html', filename=filename, content=content)

# 删除文件
@app.route('/delete/<filename>')
def delete_file(filename):
    ssh = connect_to_server()
    sftp = ssh.open_sftp()

    # 确定文件所在路径
    file_path = os.path.join(ENABLED_PATH, filename)
    if not file_exists(sftp, file_path):
        file_path = os.path.join(DISABLED_PATH, filename)
    
    sftp.remove(file_path)
    sftp.close()
    ssh.close()
    return redirect(url_for('index'))

# 上传文件
@app.route('/upload', methods=['POST'])
def upload_file():
    ssh = connect_to_server()
    sftp = ssh.open_sftp()
    file = request.files['file']
    file_path = os.path.join(ENABLED_PATH, file.filename)  # 默认存储在启用目录
    sftp.putfo(file.stream, file_path)
    sftp.close()
    ssh.close()
    return redirect(url_for('index'))

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    threading.Timer(1, open_browser).start()  # 启动浏览器
    app.run()
