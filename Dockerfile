# 使用單一階段構建，基於 Python
FROM python:3.11-bullseye
WORKDIR /app

# 設定 pip
RUN mkdir -p /root/.pip && \
    echo "[global]" > /root/.pip/pip.conf && \
    echo "trusted-host = pypi.org files.pythonhosted.org" >> /root/.pip/pip.conf && \
    echo "timeout = 1000" >> /root/.pip/pip.conf

# 安裝基本工具和必要庫
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget gnupg unzip curl ca-certificates \
    fonts-noto-cjk fonts-noto-cjk-extra \
    fonts-arphic-ukai fonts-arphic-uming \
    fonts-ipafont-mincho fonts-ipafont-gothic fonts-unfonts-core \
    xvfb x11vnc fluxbox xterm \
    libnss3 libgconf-2-4 libfontconfig1 libxi6 libxshmfence1 \
    libxtst6 fonts-liberation libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libgdk-pixbuf2.0-0 libgtk-3-0 libgbm1 && \
    rm -rf /var/lib/apt/lists/*

# 安裝 Chrome
RUN wget -q --no-check-certificate -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# 檢查安裝的 Chrome 版本並下載匹配的 ChromeDriver
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1-3) && \
    echo "Installed Chrome version: $CHROME_VERSION" && \
    CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION") && \
    echo "ChromeDriver version to download: $CHROMEDRIVER_VERSION" && \
    wget --no-check-certificate -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip" && \
    unzip /tmp/chromedriver.zip -d /tmp/ && \
    mv /tmp/chromedriver /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip && \
    echo "ChromeDriver installation completed" && \
    echo "ChromeDriver version:" && \
    chromedriver --version

# 創建啟動腳本，用於啟動 Xvfb
RUN echo '#!/bin/bash\n\
# 移除之前可能存在的 X 伺服器鎖檔案\n\
rm -f /tmp/.X*-lock\n\
rm -f /tmp/.X11-unix/X*\n\
\n\
# 啟動 Xvfb\n\
Xvfb :99 -screen 0 1920x1080x24 &\n\
export DISPLAY=:99\n\
\n\
# 等待 Xvfb 啟動\n\
sleep 2\n\
\n\
# 列出 ChromeDriver 和 Chrome 版本\n\
echo "ChromeDriver version:"\n\
chromedriver --version\n\
echo "Chrome version:"\n\
google-chrome --version\n\
\n\
# 執行主程式\n\
exec "$@"\n\
' > /usr/local/bin/start-xvfb.sh && chmod +x /usr/local/bin/start-xvfb.sh

# 安裝Python依賴
COPY requirements.txt .
RUN pip --trusted-host pypi.org --trusted-host files.pythonhosted.org --default-timeout=1000 install --upgrade pip && \
    pip --trusted-host pypi.org --trusted-host files.pythonhosted.org --default-timeout=1000 install -r requirements.txt

# 建立下載資料夾
RUN mkdir -p /app/downloads && chmod 777 /app/downloads

# 環境變數
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

# 使用啟動腳本
ENTRYPOINT ["/usr/local/bin/start-xvfb.sh"]
CMD ["python", "scrape_and_print.py"]