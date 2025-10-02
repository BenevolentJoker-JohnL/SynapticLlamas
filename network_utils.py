import socket
import logging
import ipaddress
from typing import Optional, List

logger = logging.getLogger(__name__)


def get_local_ip() -> Optional[str]:
    """Get the local IP address of this machine."""
    try:
        # Connect to an external server to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        # Doesn't actually connect, just determines route
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        # Fallback: try to get from hostname
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if local_ip != '127.0.0.1':
                return local_ip
        except Exception:
            pass
    return None


def get_network_cidr(ip_address: str, netmask: str = "255.255.255.0") -> str:
    """
    Convert IP and netmask to CIDR notation.

    Args:
        ip_address: IP address (e.g., '192.168.1.100')
        netmask: Network mask (default /24 = 255.255.255.0)

    Returns:
        CIDR notation (e.g., '192.168.1.0/24')
    """
    try:
        # Convert netmask to prefix length
        netmask_parts = netmask.split('.')
        binary = ''.join([bin(int(x))[2:].zfill(8) for x in netmask_parts])
        prefix_len = binary.count('1')

        # Create network from IP and prefix
        network = ipaddress.IPv4Network(f"{ip_address}/{prefix_len}", strict=False)
        return str(network)
    except Exception as e:
        logger.error(f"Error calculating CIDR: {e}")
        return None


def detect_local_network() -> Optional[str]:
    """
    Automatically detect the local network in CIDR notation.

    Returns:
        CIDR notation of local network (e.g., '192.168.1.0/24')
    """
    local_ip = get_local_ip()

    if not local_ip:
        logger.warning("Could not detect local IP address")
        return None

    logger.info(f"Detected local IP: {local_ip}")

    # Assume /24 subnet (most common for home/office networks)
    cidr = get_network_cidr(local_ip, "255.255.255.0")

    if cidr:
        logger.info(f"Detected network: {cidr}")
        return cidr

    return None


def get_all_network_interfaces() -> List[dict]:
    """
    Get all network interfaces and their info.

    Returns:
        List of dicts with interface info
    """
    import netifaces

    interfaces = []

    try:
        for interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)

            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr.get('addr')
                    netmask = addr.get('netmask')

                    if ip and ip != '127.0.0.1':
                        cidr = get_network_cidr(ip, netmask) if netmask else None
                        interfaces.append({
                            'interface': interface,
                            'ip': ip,
                            'netmask': netmask,
                            'cidr': cidr
                        })
    except ImportError:
        logger.debug("netifaces not available, using fallback")
        # Fallback without netifaces
        local_ip = get_local_ip()
        if local_ip:
            interfaces.append({
                'interface': 'default',
                'ip': local_ip,
                'netmask': '255.255.255.0',
                'cidr': get_network_cidr(local_ip, '255.255.255.0')
            })

    return interfaces


def suggest_scan_ranges() -> List[str]:
    """
    Suggest network ranges to scan based on local interfaces.

    Returns:
        List of CIDR ranges to scan
    """
    ranges = []

    # Try to get all interfaces
    interfaces = get_all_network_interfaces()

    for iface in interfaces:
        if iface.get('cidr'):
            ranges.append(iface['cidr'])

    # If no interfaces found, use auto-detect
    if not ranges:
        auto_cidr = detect_local_network()
        if auto_cidr:
            ranges.append(auto_cidr)

    # Deduplicate
    return list(set(ranges))
