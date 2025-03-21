# LS증권 VI 모니터링 프로그램

LS증권 API를 사용하여 주식 시장의 VI(Volatility Interruption) 발동을 실시간으로 모니터링하고, VI 발동 종목의 실시간 체결가를 감시하는 프로그램입니다.

## 주요 기능

- 실시간 VI 발동/해제 모니터링
- VI 발동 종목의 실시간 체결가 감시
- VI 해제 후 1분간 추가 모니터링
- 자동 재연결 기능
- 거래소별(KRX/KOSDAQ) 실시간 데이터 처리

## 설치 방법

1. 필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

2. 환경 변수 설정:
`.env` 파일을 생성하고 다음 내용을 입력하세요:
```
LS_APP_KEY=your_app_key
LS_SECRET_KEY=your_secret_key
```

## 실행 방법

```bash
python main.py
```

## VI 상태 설명

- 🔓 VI 해제 (0)
- 🔒 정적 VI 발동 (1)
- 🔒 동적 VI 발동 (2)
- 🔒 정적+동적 VI 동시 발동 (3)

## 주의사항

- LS증권 API 키가 필요합니다.
- 실시간 데이터는 WebSocket을 통해 수신됩니다.
- VI 해제 후 1분간 추가 모니터링이 진행됩니다.
- 프로그램 종료는 Ctrl+C를 사용하세요.

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. 