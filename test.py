
# python script to test MASQUE proxy at localhost
# only supports linux

'''
我刚刚读了一下masquerade仓库，修正一下我之前说的：
server不是standalone，它也是一个proxy，
client则是提供了http/1.1和socks5的传统协议支持。

实际的运行我们需要4个组件：
一个自定义UDP server，比如一个简单的nc pingpong就可以, 比如监听localhost:12345，
一个masquerade server听4433，
一个masquerade client听8989,目标是4433，
和一个自定义tcp client,目标是8989。

运行时，masquerade client会handle incoming tcp connection，
我们需要在这个TCP connection的起始位置发一个HTTP/1.1报文
method=CONNECT， path=/something/127.0.0.1/12345/, 
这将使得masquerade client尝试和4433建立HTTP/3 on QUIC的连接,
并转发这个path, 
masquerade server会parse path的最后两级, 
也就是127.0.0.1和12345,并尝试和127.0.0.1:12345建立一个raw UDP连接. 
这样我们就实现了从自定义tcp client到自定义udp server的代理.

在HTTP/1.1报文结束后,不要关闭TCP连接, 
那么我们发送的内容都会被masquerade client封装成HTTP/3 Data frame并发给masquerade server, 
然后进一步转发给UDP Server@localhost:12345, 
nc pingpong会回应它收到的所有内容, 这些内容会沿着原路返回TCP client, 然后我们在TCP client上应该recv到我们发出的内容. 

至于怎么设计性能指标，我们可以下周再说，但我感觉这周跑通应该是可以的。
'''



import time
import os
import threading
import subprocess
import socket

# 为了debug我封装了一些函数...

def now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def path_exists(path):
    path = os.path.expanduser(path)
    return os.path.exists(path)

def exec(command):
    print('executing:', command)
    os.system(command)
    time.sleep(1/10)

def start(func):
    print('starting:', func.__name__)
    thread = threading.Thread(target=func)
    thread.start()
    time.sleep(1/10)


def kill_process_on_port(port, wait=0.1):
    try:
        # 使用 lsof 命令查找监听指定端口的进程并获取其PID
        cmd = f"lsof -i :{port} -t"
        output = subprocess.check_output(cmd, shell=True)
        pids = output.decode('utf-8').split('\n')
        
        for pid in pids:
            if pid:
                pid = int(pid)
                # 终止进程
                subprocess.call(['kill', '-9', str(pid)])
                print(f"Terminated process with PID {pid}")
    except subprocess.CalledProcessError:
        print(f"No process found listening on port {port}")
    finally:
        time.sleep(wait)





# 下载编译好的masquerade，保存在~/masque-linux
if not path_exists('~/masque-linux'):
    exec('''
        cd ~
        sudo git clone https://github.com/dx2102/masque-linux.git
    ''')
    time.sleep(4)

# 启动masquerade server
# 结尾带&的命令会在后台运行
print('\n\n')
kill_process_on_port(4433)
exec('''
cd ~/masque-linux
export RUST_LOG=error
./server localhost:4433 &
''')

# 启动masquerade client
print('\n\n')
kill_process_on_port(8989)
exec('''
cd ~/masque-linux
export RUST_LOG=error
./client localhost:4433 localhost:8989 http &
''')

# 启动UDP echo server
print('\n\n')
@start
def tcp_echo_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 12345))
    sock.listen(5)
    # loop
    conn, addr = sock.accept()
    print('TCP echo server accepted connection from', addr)
    while True:
        data = conn.recv(1024)
        if not data:
            print('TCP echo server connection closed')
            break
        print('TCP echo server received and sent:', data)
        conn.send(data)
    conn.close()

# 启动TCP client，向masquerade client (8989端口)发起http代理的连接
print('\n\n')
@start
def tcp_client():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', 8989))
    def send(data):
        sock.send(data.encode() + b'\r\n')
        print('TCP client sent: ', data)
    '''
    CONNECT /something/127.0.0.1/12345/ HTTP/1.1
    Host: example.com
    '''
    send('CONNECT localhost:12345/something/127.0.0.1/12345/ HTTP/1.1')
    send('Host: localhost:12345')
    
    send('\r\n\r\n')
    time.sleep(0.1)
    send('hello')
    # 看看有没有得到echo
    while True:
        data = sock.recv(1024)
        if not data:
            print('TCP client connection closed')
            break
        print('TCP client received: ', data)
    sock.close()




time.sleep(999999999)






















