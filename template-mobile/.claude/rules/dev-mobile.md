# Dev 지시문 — Expo 모바일 보강

`harness-final` 공통 코딩 규칙을 그대로 따른다. 아래는 Expo/React Native 고유의 추가 주의사항만 다룬다.

## 웹과 다른 점 (실수 빈발 지점)
- **DOM이 없다.** `div`, `span`, `onClick`이 아니라 `View`, `Text`, `onPress`다. 웹 React 습관으로 코드를 쓰면 안 된다.
- **localStorage 없음.** 영속 저장은 `AsyncStorage`나 파일시스템. (단, 이 앱은 히스토리 정도라 저장 필요 최소화.)
- **CSS 파일 없음.** 스타일은 `StyleSheet.create`. 웹 CSS 클래스 사고를 가져오지 않는다.

## 네이티브 모듈 다루기
- QR 디코드·카메라·이미지 선택은 네이티브 모듈에 의존한다. 새 네이티브 의존성을 추가하면 **반드시 `npx expo run:ios` 재빌드**가 필요하다 (JS만 바꾸는 fast refresh로는 반영 안 됨).
- 네이티브 모듈 추가 시 app.json의 권한 설명(Info.plist 키)도 함께 갱신한다. 빠뜨리면 런타임 크래시.

## QR 디코드 로직 격리 (테스트 가능성)
- 디코드 핵심 로직은 `src/lib/qr/`에 UI와 분리해 둔다.
- 목표: 시뮬레이터 없이 **테스트 이미지 파일 입력 → 디코드 결과 출력**을 유닛테스트할 수 있어야 한다.
- 이렇게 격리해야 빠른 Back-pressure(Stop Hook)에서 핵심 로직이 검증된다. UI에 디코드를 직접 박으면 시뮬레이터 없이는 테스트 불가가 되어 2단계 구조가 무너진다.

## TDD 적용 (vertical slice)
- 디코드 기능: 테스트 QR 이미지 1개에 대한 테스트 작성 → 통과시키는 최소 구현 → 다음 케이스(빈 이미지, 손상 이미지) 순.
- 모든 테스트를 먼저 쓰는 horizontal slicing 금지 (공통 규칙).

## 라이브러리 (ADR-002에서 확정)
QR 디코드는 **react-native-vision-camera**를 Expo config plugin으로 쓴다 (저장 이미지 스캔 지원).
본격 구현 전, ADR-002의 **스파이크**(테스트 QR 이미지 1장 디코드 성공)를 사용할 Expo SDK 버전에서 먼저 통과시킬 것. 스파이크 실패 시 ADR-002 갱신 후 재논의 — 임의로 다른 라이브러리로 갈아타지 않는다.
