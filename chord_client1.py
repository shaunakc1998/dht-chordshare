import socket
import threading
import pickle
import sys
import time
import hashlib
import os
from collections import OrderedDict
from enum import Enum
from datetime import datetime
from config import IP_ADD, PORT_NUM, BUFFER_SIZE, MAXIMUM_BITS, TOTAL_NODES, ConsistencyStrategy, ConcurrencyControl

def calculate_hash(key):
    sha1_hash = hashlib.sha1(key.encode()).hexdigest()
    return int(sha1_hash, 16) % TOTAL_NODES

class ChordNode:
    def __init__(self, ip, port, buffer_size=BUFFER_SIZE, consistency_strategy=ConsistencyStrategy.EVENTUAL, concurrency_control=ConcurrencyControl.OPTIMISTIC):
        self.files = []
        self.ip_address = ip
        self.port_number = port
        self.node_address = (ip, port)
        self.node_id = calculate_hash(ip + ":" + str(port))
        self.predecessor = self.node_address
        self.predecessor_id = self.node_id
        self.successor = self.node_address
        self.successor_id = self.node_id
        self.finger_table = OrderedDict()
        self.consistency_strategy = consistency_strategy
        self.concurrency_control = concurrency_control
        self.locks = {}
        self.buffer_size = buffer_size

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((ip, port))
            self.server_socket.listen()
        except socket.error:
            print("Failed to open socket")

    def discover_resources(self, resource_name):
        resource_id = calculate_hash(resource_name)
        recv_ip_port = self.get_successor_node(self.successor, resource_id)
        return recv_ip_port

    def replicate_file(self, filename, consistency_strategy=None):
        if consistency_strategy is None:
            consistency_strategy = self.consistency_strategy

        if consistency_strategy == ConsistencyStrategy.EVENTUAL:
            self.replicate_file_eventual(filename)
        elif consistency_strategy == ConsistencyStrategy.SEQUENTIAL:
            self.replicate_file_sequential(filename)
        elif consistency_strategy == ConsistencyStrategy.LINEARIZABLE:
            self.replicate_file_linearizable(filename)

    def replicate_file_eventual(self, filename):
        file_id = calculate_hash(filename)
        successor_nodes = self.fetch_succ_nodes(file_id, 3)
        for node in successor_nodes:
            self.upload_file(filename, node, replicate=False)

    def replicate_file_sequential(self, filename):
        file_id = calculate_hash(filename)
        successor_nodes = self.fetch_succ_nodes(file_id, 3)
        for node in successor_nodes:
            self.acq_lock(filename)
            self.upload_file(filename, node, replicate=False)
            self.release_lock(filename)

    def replicate_file_linearizable(self, filename):
        file_id = calculate_hash(filename)
        successor_nodes = self.fetch_succ_nodes(file_id, 3)
        self.acq_lock(filename)
        for node in successor_nodes:
            self.upload_file(filename, node, replicate=True)
        self.release_lock(filename)

    def acq_lock(self, resource_name):
        if self.concurrency_control == ConcurrencyControl.OPTIMISTIC:
            self.acq_lock_opt(resource_name)
        elif self.concurrency_control == ConcurrencyControl.PESSIMISTIC:
            self.acq_lock_pess(resource_name)

    def acq_lock_opt(self, resource_name):
        self.locks[resource_name] = datetime.now()

    def acq_lock_pess(self, resource_name):
        resource_id = calculate_hash(resource_name)
        responsible_node = self.get_successor_node(self.successor, resource_id)
        if responsible_node == self.node_address:
            self.locks[resource_name] = datetime.now()
        else:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.connect(responsible_node)
            s_list = [6, resource_name]
            peer_socket.sendall(pickle.dumps(s_list))
            response = pickle.loads(peer_socket.recv(self.buffer_size))
            if response == "LockGranted":
                self.locks[resource_name] = datetime.now()
            peer_socket.close()

    def release_lock(self, resource_name):
        if resource_name in self.locks:
            del self.locks[resource_name]

    def fetch_succ_nodes(self, key_id, num_nodes):
        nodes = [self.node_address]
        curr_node = self.successor
        for _ in range(num_nodes - 1):
            if curr_node == self.node_address:
                break
            nodes.append(curr_node)
            curr_node = self.get_successor_node(curr_node, key_id)
        return nodes

    def startSocketThread(self):
        while True:
            try:
                connection, address = self.server_socket.accept()
                connection.settimeout(200)
                threading.Thread(target=self.conn_handler, args=(connection, address)).start()
            except socket.error:
                pass

    def conn_handler(self, connection, address):
        r_list = pickle.loads(connection.recv(self.buffer_size))
        connection_type = r_list[0]

        if connection_type == 0:
            self.join_handler(connection, address, r_list)
            self.displayMenu()
        elif connection_type == 1:
            self.f_trans_handler(connection, address, r_list)
            self.displayMenu()
        elif connection_type == 2:
            connection.sendall(pickle.dumps(self.predecessor))
        elif connection_type == 3:
            self.id_look_handler(connection, address, r_list)
        elif connection_type == 4:
            if r_list[1] == 1:
                self.modify_successor(r_list)
            else:
                self.modify_predecessor(r_list)
        elif connection_type == 5:
            self.modify_ftable()
            connection.sendall(pickle.dumps(self.successor))
        elif connection_type == 6:
            resource_name = r_list[1]
            self.lock_req_handler(connection, resource_name)
        else:
            print("Problem with connection type")

    def lock_req_handler(self, connection, resource_name):
        resource_id = calculate_hash(resource_name)
        responsible_node = self.get_successor_node(self.successor, resource_id)
        if responsible_node == self.node_address:
            if resource_name not in self.locks:
                self.locks[resource_name] = datetime.now()
                connection.sendall(pickle.dumps("LockGranted"))
            else:
                connection.sendall(pickle.dumps("LockDenied"))
        else:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.connect(responsible_node)
            peer_socket.sendall(pickle.dumps([6, resource_name]))
            response = pickle.loads(peer_socket.recv(self.buffer_size))
            connection.sendall(pickle.dumps(response))
            peer_socket.close()

    def join_handler(self, connection, address, r_list):
        if r_list:
            peer_ip_port = r_list[1]
            peer_id = calculate_hash(peer_ip_port[0] + ":" + str(peer_ip_port[1]))
            old_predecessor = self.predecessor
            self.predecessor = peer_ip_port
            self.predecessor_id = peer_id
            s_list = [old_predecessor]
            connection.sendall(pickle.dumps(s_list))
            time.sleep(0.1)
            self.modify_ftable()
            self.modify_peer_ftable()

    def f_trans_handler(self, connection, address, r_list):
        choice = r_list[1]
        filename = r_list[2]
        file_id = calculate_hash(filename)

        if choice == 0:
            print("Download request for file:", filename)
            if filename not in self.files:
                connection.send("NotFound".encode('utf-8'))
                print("File not found")
            else:
                connection.send("Found".encode('utf-8'))
                self.send_file(connection, filename)
        elif choice == 1 or choice == -1:
            print("Receiving file:", filename)
            print("Uploading file ID:", file_id)
            self.files.append(filename)
            self.receive_file(connection, filename)
            print("Upload complete")
            if choice == 1:
                if self.node_address != self.successor:
                    self.upload_file(filename, self.successor, False)

    def id_look_handler(self, connection, address, r_list):
        key_id = r_list[1]
        s_list = []
        if self.node_id == key_id:
            s_list = [0, self.node_address]
        elif self.successor_id == self.node_id:
            s_list = [0, self.node_address]
        elif self.node_id > key_id:
            if self.predecessor_id < key_id:
                s_list = [0, self.node_address]
            elif self.predecessor_id > self.node_id:
                s_list = [0, self.node_address]
            else:
                s_list = [1, self.predecessor]
        else:
            if self.node_id > self.successor_id:
                s_list = [0, self.successor]
            else:
                value = ()
                for key, value in self.finger_table.items():
                    if key >= key_id:
                        break
                value = self.successor
                s_list = [1, value]
        connection.sendall(pickle.dumps(s_list))

    def modify_successor(self, r_list):
        new_successor = r_list[2]
        self.successor = new_successor
        self.successor_id = calculate_hash(new_successor[0] + ":" + str(new_successor[1]))

    def modify_predecessor(self, r_list):
        new_predecessor = r_list[2]
        self.predecessor = new_predecessor
        self.predecessor_id = calculate_hash(new_predecessor[0] + ":" + str(new_predecessor[1]))

    def start(self):
        threading.Thread(target=self.startSocketThread, args=()).start()
        threading.Thread(target=self.ping_successor, args=()).start()

        while True:
            print("Listening to other clients")
            self.client_handler()

    def ping_successor(self):
        while True:
            time.sleep(2)
            if self.node_address == self.successor:
                continue
            try:
                peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                peer_socket.connect(self.successor)
                peer_socket.sendall(pickle.dumps([2]))
                recv_predecessor = pickle.loads(peer_socket.recv(self.buffer_size))
            except:
                print("\nNode Crashed, fixing it!")
                new_successor_found = False
                value = ()
                for key, value in self.finger_table.items():
                    if value[0] != self.successor_id:
                        new_successor_found = True
                        break
                if new_successor_found:
                    self.successor = value[1]
                    self.successor_id = calculate_hash(self.successor[0] + ":" + str(self.successor[1]))
                    peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    peer_socket.connect(self.successor)
                    peer_socket.sendall(pickle.dumps([4, 0, self.node_address]))
                    peer_socket.close()
                else:
                    self.predecessor = self.node_address
                    self.predecessor_id = self.node_id
                    self.successor = self.node_address
                    self.successor_id = self.node_id
                self.modify_ftable()
                self.modify_peer_ftable()
                self.displayMenu()

    def client_handler(self):
        self.displayMenu()
        user_choice = input("Choose an action: ")

        if user_choice == "1":
            ip_port = input("Enter IP and port (format: IP:PORT): ")
            try:
                ip, port = ip_port.split(":")
                self.conn_req_handler(ip, int(port))
            except ValueError:
                print("Invalid format. Please use the format IP:PORT.")
        elif user_choice == "2":
            self.leave_network()
        elif user_choice == "3":
            filename = input("Enter the name of the file you want to upload: ")
            file_id = calculate_hash(filename)
            recv_ip_port = self.get_successor_node(self.successor, file_id)
            self.upload_file(filename, recv_ip_port, True)
        elif user_choice == "4":
            filename = input("Enter the name of the file you want to download: ")
            self.download_file(filename)
        elif user_choice == "5":
            print(f"My ID: {self.node_id}, Predecessor: {self.predecessor_id}, Successor: {self.successor_id}")
        else:
            print("Invalid choice. Please try again.")


    def conn_req_handler(self, ip, port):
        try:
            recv_ip_port = self.get_successor_node((ip, port), self.node_id)
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.connect(recv_ip_port)
            s_list = [0, self.node_address]
            peer_socket.sendall(pickle.dumps(s_list))
            r_list = pickle.loads(peer_socket.recv(self.buffer_size))
            self.predecessor = r_list[0]
            self.predecessor_id = calculate_hash(self.predecessor[0] + ":" + str(self.predecessor[1]))
            self.successor = recv_ip_port
            self.successor_id = calculate_hash(recv_ip_port[0] + ":" + str(recv_ip_port[1]))
            s_list = [4, 1, self.node_address]
            peer_socket2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket2.connect(self.predecessor)
            peer_socket2.sendall(pickle.dumps(s_list))
            peer_socket2.close()
            peer_socket.close()
        except socket.error:
            print("Socket error. Recheck IP/Port.")

    def leave_network(self):
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.connect(self.successor)
        peer_socket.sendall(pickle.dumps([4, 0, self.predecessor]))
        peer_socket.close()
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.connect(self.predecessor)
        peer_socket.sendall(pickle.dumps([4, 1, self.successor]))
        peer_socket.close()
        print("Files present:", self.files)
        print("Replicating files to other nodes before leaving")
        for filename in self.files:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.connect(self.successor)
            s_list = [1, 1, filename]
            peer_socket.sendall(pickle.dumps(s_list))
            with open(filename, 'rb') as file:
                peer_socket.recv(self.buffer_size)
                self.send_file(peer_socket, filename)
                peer_socket.close()
                print("File replicated")
            peer_socket.close()
        self.modify_peer_ftable()
        self.predecessor = (self.ip_address, self.port_number)
        self.predecessor_id = self.node_id
        self.successor = (self.ip_address, self.port_number)
        self.successor_id = self.node_id
        self.finger_table.clear()
        print(self.node_address, "has left the network")

    def upload_file(self, filename, recv_ip_port, replicate):
        print("Uploading file", filename)
        s_list = [1]
        if replicate:
            s_list.append(1)
        else:
            s_list.append(-1)
        try:
            file = open(filename, 'rb')
            file.close()
            s_list = s_list + [filename]
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(recv_ip_port)
            client_socket.sendall(pickle.dumps(s_list))
            self.send_file(client_socket, filename)
            client_socket.close()
            print("File uploaded")
        except IOError:
            print("File not in directory")
        except socket.error:
            print("Error in uploading file")

    def download_file(self, filename):
        print("Downloading file", filename)
        file_id = calculate_hash(filename)
        recv_ip_port = self.get_successor_node(self.successor, file_id)
        s_list = [1, 0, filename]
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(recv_ip_port)
        client_socket.sendall(pickle.dumps(s_list))
        file_data = client_socket.recv(self.buffer_size)
        if file_data == b"NotFound":
            print("File not found:", filename)
        else:
            print("Receiving file:", filename)
            self.receive_file(client_socket, filename)

    def get_successor_node(self, address, key_id):
        r_list = [1, address]
        recv_ip_port = r_list[1]
        while r_list[0] == 1:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                peer_socket.connect(recv_ip_port)
                s_list = [3, key_id]
                peer_socket.sendall(pickle.dumps(s_list))
                r_list = pickle.loads(peer_socket.recv(self.buffer_size))
                recv_ip_port = r_list[1]
                peer_socket.close()
            except socket.error:
                print("Connection denied while getting Successor")
        return recv_ip_port

    def modify_ftable(self):
        for i in range(MAXIMUM_BITS):
            entry_id = (self.node_id + (2 ** i)) % TOTAL_NODES
            if self.successor == self.node_address:
                self.finger_table[entry_id] = (self.node_id, self.node_address)
                continue
            recv_ip_port = self.get_successor_node(self.successor, entry_id)
            recv_id = calculate_hash(recv_ip_port[0] + ":" + str(recv_ip_port[1]))
            self.finger_table[entry_id] = (recv_id, recv_ip_port)

    def modify_peer_ftable(self):
        current_node = self.successor
        while True:
            if current_node == self.node_address:
                break
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                peer_socket.connect(current_node)
                peer_socket.sendall(pickle.dumps([5]))
                current_node = pickle.loads(peer_socket.recv(self.buffer_size))
                peer_socket.close()
                if current_node == self.successor:
                    break
            except socket.error:
                print("Connection denied")

    def send_file(self, connection, filename):
        print("Sending file:", filename)
        if not os.path.exists(filename):
            print("Error: File not found")
            connection.sendall(b"FileNotFound")
            return
        try:
            with open(filename, 'rb') as file:
                data = file.read()
                file_size = len(data)
                connection.sendall(file_size.to_bytes(4, byteorder='big'))
                connection.sendall(data)
        except FileNotFoundError:
            print("Error: File not found")

    def receive_file(self, connection, filename):
        print("Receiving file:", filename)
        try:
            file_size = int.from_bytes(connection.recv(4), byteorder='big')
            print("Expected file size:", file_size)
            data = b""
            received_size = 0
            while received_size < file_size:
                packet = connection.recv(self.buffer_size)
                data += packet
                received_size += len(packet)
                print("Received size so far:", received_size)
            with open(filename, 'wb') as file:
                file.write(data)
            print("File received:", filename)
            print("Received data:", data)
        except IOError:
            print("Error: Unable to write file")
        finally:
            connection.close()

    def displayMenu(self):
        menu_title = "Main Menu"
        options = {
            "1": "Connect to network",
            "2": "Leave network",
            "3": "Upload file to network",
            "4": "Download file from network"
        }

        width = max(len(option) for option in options.values()) + 4

        print("\n" + "*" * (width + len(menu_title) + 4))
        print(f"* {menu_title.center(width)} *")
        print("*" * (width + len(menu_title) + 4))

        for key, value in options.items():
            print(f"* {key}. {value.ljust(width)} *")

        print("*" * (width + len(menu_title) + 4))
        print("Enter your choice: ", end='')


def initialize_node(ip, port, buffer):
    chord_node = ChordNode(ip, port, buffer_size=buffer)
    chord_node.start()

if __name__ == "__main__":
    if len(sys.argv) == 4:
        IP = sys.argv[1]
        PORT_NUM = int(sys.argv[2])
        BUFFER_SIZE = int(sys.argv[3])
    else:
        IP = IP_ADD
        PORT_NUM = PORT_NUM
        BUFFER_SIZE = BUFFER_SIZE

    initialize_node(IP, PORT_NUM, BUFFER_SIZE)
