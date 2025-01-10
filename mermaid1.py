import json


def generate_mermaid(json_data):
    lines = ["graph TD"]
    for node, details in json_data.items():
        node_name = f'{node}["{node}<br>IP: {details["node_details"].get("ip", "")}<br>Platform: {details["node_details"].get("platform", "")}"]'
        lines.append(f"    {node_name}")

        for peer, peer_details in details.get("peers", {}).items():
            peer_name = f'{peer}["{peer}<br>IP: {peer_details.get("ip", "")}<br>Platform: {peer_details.get("platform", "")}"]'
            if peer_name not in lines:
                lines.append(f"    {peer_name}")

            for connection in peer_details.get("connections", []):
                conn_str = f' -- "{connection[0]} - {connection[1]}" --> '
                lines.append(f"    {node}{conn_str}{peer}")

    return "\n".join(lines)


# Load the JSON data from a file or directly as a string
json_input = '''
{
  "uspc-cr-core": {
    "node_details": {
      "ip": "10.80.16.1",
      "platform": "C9300-48UXM"
    },
    "peers": {
      "uspc-cr-lan-sw-02": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Te1/0/46",
            "Gi1/0/26"
          ],
          [
            "Te2/0/46",
            "Gi1/0/25"
          ]
        ]
      },
      "uspc-cr-lan-sw-03": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Te1/0/45",
            "Gi1/0/26"
          ],
          [
            "Te2/0/45",
            "Gi1/0/25"
          ]
        ]
      },
      "uspc-cr-swl-01": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Te1/1/4",
            "Te2/1/1"
          ],
          [
            "Te2/1/4",
            "Te1/1/1"
          ]
        ]
      },
      "uspc-idf01-lan-sw-01": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Te1/1/3",
            "Te2/1/1"
          ],
          [
            "Te2/1/3",
            "Te1/1/1"
          ]
        ]
      },
      "uspc-fwt-01": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Te1/0/41",
            "Eth1/2"
          ]
        ]
      },
      "s2node": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "tw1/0/12",
            "f0b5.d1d7.66e3"
          ]
        ]
      }
    }
  },
  "uspc-cr-lan-sw-02": {
    "node_details": {
      "ip": "10.80.29.14",
      "platform": "WS-C2960X-24TD-L"
    },
    "peers": {
      "uspc-cr-core": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi1/0/26",
            "Te1/0/46"
          ],
          [
            "Gi1/0/25",
            "Te2/0/46"
          ]
        ]
      }
    }
  },
  "uspc-cr-lan-sw-03": {
    "node_details": {
      "ip": "10.80.29.15",
      "platform": "WS-C2960X-24TD-L"
    },
    "peers": {
      "uspc-cr-core": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi1/0/26",
            "Te1/0/45"
          ],
          [
            "Gi1/0/25",
            "Te2/0/45"
          ]
        ]
      }
    }
  },
  "uspc-cr-swl-01": {
    "node_details": {
      "ip": "10.80.29.10",
      "platform": "C9200-48PXG"
    },
    "peers": {
      "uspc-floor-sw-03": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi1/0/6",
            "Gi0/10"
          ]
        ]
      },
      "uspc-floor-sw-02": {
        "ip": "",
        "platform": "WS-C3560CX-8PC-S",
        "connections": [
          [
            "Gi1/0/5",
            "Gi0/10"
          ]
        ]
      },
      "uspc-cr-core": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Te1/1/1",
            "Te2/1/4"
          ],
          [
            "Te2/1/1",
            "Te1/1/4"
          ]
        ]
      },
      "surveillance_camera": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi5/0/1",
            "e430.2256.8808"
          ]
        ]
      },
      "uspc-wap-07": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi1/0/2",
            "6026.efc2.3f88"
          ]
        ]
      },
      "uspc-wap-09": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi1/0/3",
            "6026.efc2.2fa4"
          ]
        ]
      },
      "uspc-wap-08": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi1/0/1",
            "6026.efc2.38da"
          ]
        ]
      },
      "uspc-wap-10": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi1/0/4",
            "6026.efc2.4bde"
          ]
        ]
      },
      "pnm-9081vq": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi5/0/12",
            "0009.185b.d8d9"
          ]
        ]
      }
    }
  },
  "uspc-idf01-lan-sw-01": {
    "node_details": {
      "ip": "10.80.29.37",
      "platform": "C9200-48PXG"
    },
    "peers": {
      "uspc-cr-core": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Te1/1/1",
            "Te2/1/3"
          ],
          [
            "Te2/1/1",
            "Te1/1/3"
          ]
        ]
      },
      "uspc-wap-04": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi1/0/36",
            "6026.efc2.3fac"
          ]
        ]
      },
      "uspc-wap-02": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi2/0/36",
            "6026.efc2.49a6"
          ]
        ]
      },
      "uspc-wap-06": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi2/0/34",
            "cc88.c7cf.8762"
          ]
        ]
      },
      "uspc-wap-01": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi1/0/38",
            "6026.efc2.4a0e"
          ]
        ]
      },
      "uspc-wap-03": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi2/0/38",
            "6026.efc2.423c"
          ]
        ]
      },
      "uspc-wap-05": {
        "ip": "",
        "platform": "",
        "connections": [
          [
            "Gi1/0/34",
            "cc88.c7cf.8ca2"
          ]
        ]
      }
    }
  },
  "uspc-floor-sw-03": {
    "node_details": {
      "ip": "10.80.29.18",
      "platform": "WS-C3560CX-8PC-S"
    },
    "peers": {}
  },
  "uspc-floor-sw-02": {
    "node_details": {
      "ip": "10.80.29.17",
      "platform": "WS-C3560CX-8PC-S"
    },
    "peers": {}
  }
}

'''  # Truncated for brevity. Use your full JSON data here.

data = json.loads(json_input)
mermaid_code = generate_mermaid(data)

# Output the result
print(mermaid_code)
