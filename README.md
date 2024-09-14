# Chord Algorithm File Sharing System

This project implements a decentralized peer-to-peer file sharing system using the Chord distributed hash table (DHT) protocol. It allows for dynamic node management, efficient file lookup, replication for fault tolerance, and supports various concurrency control mechanisms.

## Features

- **Decentralized Architecture**: No central servers, eliminating single points of failure and scaling efficiently.
- **Efficient Lookup**: Uses Chord protocol's logarithmic lookup for fast file location.
- **File Replication**: Enhances data availability by replicating files across multiple successor nodes.
- **Concurrency Control**: Supports file locking and leases to enable parallel file access.
- **Dynamic Node Management**: Nodes can join or leave without disrupting the network.
- **Failure Handling**: Periodic checks and stabilization routines maintain consistency.
- **Scalability**: Logarithmic routing complexity helps the system scale with the number of nodes.

## System Workflow

Below is a high-level overview of the system's operations and control flow in the Chord network.

![System Workflow](https://github.com/ShaunakChaudhary/ChordShare/blob/main/docs/Chord%20Algorithm%20File%20Sharing.pdf)

## Use Case Diagram

This diagram shows user interactions with the Chord node system.

![Use Case Diagram](https://github.com/ShaunakChaudhary/ChordShare/blob/main/docs/Interaction%20between%20user%20and%20system%20functions.png)

## File Management

The sequence diagram below details file upload, download, and replication processes.

![File Management](https://github.com/ShaunakChaudhary/ChordShare/blob/main/docs/File%20Uploading%2C%20Downloading%20%26%20Replication.png)

## User Interface

### Display Menu
Presents a list of operations available to the user.
![Display Menu](https://github.com/ShaunakChaudhary/ChordShare/blob/main/docs/User%20Interface.jpg)

### Uploading File
Simplifies file sharing across the network.
![Uploading File](https://github.com/ShaunakChaudhary/ChordShare/blob/main/docs/Upload.png)

### Downloading File
Facilitates file downloads from the network.
![Downloading File](https://github.com/ShaunakChaudhary/ChordShare/blob/main/docs/Download.png)

### Crash Handling
Informs users during a node crash and initiates recovery.
![Crash Handling](https://github.com/ShaunakChaudhary/ChordShare/blob/main/docs/Crash.png)

## Installation and Usage

Clone the repository:

```bash
[git clone https://github.com/ShaunakChaudhary/ChordShare.git]
```

Install the required dependencies (e.g., Python, if applicable).

Configure the network settings (IP addresses, port numbers) for the nodes.

Run the program on each node to join the network.

Use the provided user interface to upload, download, and manage files within the distributed system.

For detailed instructions and examples, please refer to the project's documentation.
