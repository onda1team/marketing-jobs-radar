# 마케팅 채용 레이더 (천안 · 아산 · 평택 · 안성 · 오산)

사람인 · 잡코리아 · 원티드 · 인크루트 · 잡플래닛의 **마케팅 담당자 및 마케팅 전체 직무** 공고를 자동 수집해 **연봉이 높은 순**으로 정렬하고, **GitHub Pages 웹 대시보드**로 PC/모바일 어디서든 확인할 수 있는 자동화 프로젝트입니다.

## 주요 기능
- **5개 플랫폼 통합 수집**: 사람인, 잡코리아, 원티드, 인크루트, 잡플래닛
- **지역 정밀 필터링**: 천안, 아산, 평택, 안성, 오산
- **연봉 자동 환산 & 높은 순 정렬**: 연봉/월급/시급 표기를 연봉(만원) 기준으로 환산해 높은 순으로 정렬 (미기재 공고는 하단 정렬 + `연봉 명시만` 토글 지원)
- **다른 컴퓨터·모바일에서 열람**: GitHub Actions가 매일 오전 9시(KST) 자동 수집 후 GitHub Pages에 자동 반영
- **엑셀(CSV) 다운로드 & 북마크**: 대시보드에서 바로 CSV 다운로드 및 관심 공고 별표 저장

## 로컬에서 즉시 실행하기
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m scraper.main
```
대시보드 미리보기:
```bash
python3 -m http.server 8000 --directory docs
# 브라우저에서 http://localhost:8000 접속
```

## 다른 컴퓨터에서도 보기 (GitHub Pages 3분 배포)
1. GitHub에서 새 저장소(예: `marketing-jobs-radar`)를 생성합니다. (Public 저장소면 GitHub Pages 무료)
2. 이 폴더에서 GitHub로 푸시합니다:
   ```bash
   git init
   git add .
   git commit -m "feat: initial marketing jobs radar"
   git branch -M main
   git remote add origin https://github.com/<본인아이디>/marketing-jobs-radar.git
   git push -u origin main
   ```
3. GitHub 저장소 **Settings → Pages**:
   - **Source**: `Deploy from a branch`
   - **Branch**: `main` / `/docs` 선택 후 **Save**
4. 1~2분 뒤 `https://<본인아이디>.github.io/marketing-jobs-radar/` 주소가 생성됩니다!
   - 이제 **어떤 컴퓨터·스마트폰**에서도 해당 링크로 접속해 매일 업데이트되는 연봉순 마케팅 공고를 볼 수 있습니다.
   - 수동으로 바로 새로고침하고 싶다면 GitHub 저장소의 **Actions → Update Marketing Jobs → Run workflow**를 클릭하세요.
