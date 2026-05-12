# 브라우저 상태 확인

Chrome 인스턴스들의 상태를 점검해줘.

1. 포트 9222 (Google) 연결 확인: `curl -s http://localhost:9222/json/version`
2. 포트 9223 (Meta) 연결 확인: `curl -s http://localhost:9223/json/version`
3. 포트 9224 (General) 연결 확인: `curl -s http://localhost:9224/json/version`
4. 각 인스턴스의 열린 탭 수 확인: `curl -s http://localhost:{port}/json/list | python3 -c "import sys,json; print(len(json.load(sys.stdin)))"`
5. LM Studio 서버 상태: `curl -s http://localhost:1234/v1/models`
6. 문제가 있으면 해결 방법 제시
