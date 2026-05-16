export default function SettingsPage() {
  return (
    <div className="container mx-auto space-y-4 p-6">
      <h1 className="text-display-md">Settings</h1>
      <p className="text-body-md text-muted-foreground">
        프로필, 보컬 클로닝, 알림 설정.
      </p>
      <p className="text-body-md">
        (스텁) — 추후 NextAuth 사용자 정보 + 환경설정 UI 추가.
      </p>
    </div>
  );
}
