import re
import time

import requests
import urllib3
from bs4 import BeautifulSoup

prompt = "tell me a joke"

# engineering.nyu.edu is using a self-signed certificate / entriprise signed certificate
# Disable warnings since we are intentionally skipping certificate verification for this endpoint
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://launchthenukes.engineering.nyu.edu/submit"

headers = {
    "Cookie": "user_id=4ced1eb6-b08b-42ed-a8e5-5bcf02b0de9c",
    "Referer": "https://launchthenukes.engineering.nyu.edu/dashboard"
}

payload = {
    "user_input": prompt
}

response = requests.post(url, headers=headers, data=payload, verify=False)
with open("create.html", "w") as f:
    f.write(response.content.decode("utf-8"))
print(response.text[:100])

"""const jobId = '65c2148d-9d12-4b86-b4c0-654a8a003ec6';"""
match = re.search(r"const jobId = '([^']+)';", response.text)
if not match:
    raise ValueError("Failed to extract jobId from submit response")
jobId = match.group(1)

url = f"https://launchthenukes.engineering.nyu.edu/api/job/{jobId}/status"

MAX_WAIT_TIME = 60 * 10 # 10 minutes
start_time = time.time()
while True:
    resp = requests.get(url, headers=headers, verify=False)
    with open("resp.html", "w") as f:
        f.write(resp.content.decode("utf-8"))
    if resp.status_code != 200:
        print(f"HTTP error! status: {resp.status_code}")
        time.sleep(2)
        continue
    data = resp.json()
    status = data.get('status')
    if status in ('completed', 'failed'):
        break
    # Update progress
    progress = data.get('progress')
    progress_message = data.get('progress_message')
    queue_position = data.get('queue_position')
    print(f"Status: {status}")
    if progress is not None:
        print(f"Progress: {progress}%")
    if progress_message:
        print(f"Message: {progress_message}")
    if queue_position and queue_position > 0:
        print(f"Queue position: {queue_position}")
    time.sleep(2)
    if time.time() - start_time > MAX_WAIT_TIME:
        print("Max wait time reached")
        raise Exception("Max wait time reached")

url = f"https://launchthenukes.engineering.nyu.edu/results/{jobId}"

resp = requests.get(url, headers=headers, verify=False)
html = resp.content.decode("utf-8")
with open("results.html", "w") as f:
    f.write(html)

soup = BeautifulSoup(html, "html.parser")

# Extract prompt
prompt_header = soup.find("h2", string=lambda s: s and "Original Prompt" in s)
prompt = prompt_header.find_next("p").get_text(strip=True) if prompt_header else "<unknown>"

# Extract tool calls JSON blob
tool_calls_header = soup.find("h2", string=lambda s: s and "LLM Tool Calls" in s)
tool_calls = None
if tool_calls_header:
    tool_calls_pre = tool_calls_header.find_next("pre")
    if tool_calls_pre:
        tool_calls = tool_calls_pre.get_text("\n", strip=True)

# Extract tool call results
tool_call_results = []
tool_results_header = soup.find("h2", string=lambda s: s and "Tool Call Results" in s)
if tool_results_header:
    section = tool_results_header.find_parent("div", class_="bg-white")
    if section:
        for block in section.find_all("div", class_=lambda c: c and ("rounded-lg" in c if isinstance(c, list) else "rounded-lg" in c.split())):
            name_tag = block.find("h3")
            output_pre = block.find("pre")
            if name_tag and output_pre:
                tool_call_results.append(
                    (name_tag.get_text(strip=True), output_pre.get_text("\n", strip=True))
                )

# Extract triggered servers
triggered_servers = []
triggered_header = soup.find("h2", string=lambda s: s and "Triggered MCP Servers" in s)
if triggered_header:
    section = triggered_header.find_parent("div", class_="bg-white")
    if section:
        for heading in section.find_all("h3", class_=lambda c: c and ("font-medium" in c if isinstance(c, list) else "font-medium" in c.split())):
            server_name = heading.get_text(strip=True)
            card = heading.find_parent("div", class_=lambda c: c and ("rounded-lg" in c if isinstance(c, list) else "rounded-lg" in c.split()))
            risk_tag = card.find("span", string=lambda s: s and "RISK" in s) if card else None
            risk_level = risk_tag.get_text(strip=True) if risk_tag else "UNKNOWN"
            triggered_servers.append((server_name, risk_level))

print(f"Prompt: {prompt}")
if tool_calls:
    print("LLM Tool Calls:")
    print(tool_calls)
if tool_call_results:
    print("Tool Call Results:")
    for name, result in tool_call_results:
        print(f"- {name}:\n{result}")
if triggered_servers:
    print("Triggered Servers:")
    for name, risk in triggered_servers:
        print(f"- {name} ({risk})")
else:
    print("No triggered servers found")
