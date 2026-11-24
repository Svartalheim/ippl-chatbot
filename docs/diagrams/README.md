# Diagram SKPL (PlantUML)

| File | Bagian SKPL |
|---|---|
| `usecase.puml` | §3.2.1 Use Case Diagram |
| `class-domain.puml` | §3.2.2 Class Diagram (domain) |
| `class-implementation.puml` | Lampiran: class diagram lapisan router/service |
| `activity-query.puml` | §3.2.3.1 Mengajukan Pertanyaan |
| `activity-kelola-dokumen.puml` | §3.2.3.2 Administrator Mengelola Dokumen |
| `activity-audit.puml` | §3.2.3.3 Auditor Meninjau Log Audit |
| `activity-login-logout.puml`, `activity-kelola-peran.puml`, `activity-feedback.puml` | §3.2.3.4–6 (baru) |
| `seq-*.puml` | §3.2.4 Sequence Diagram (baru) |
| `erd.puml` | §3.2.5 ERD (baru) |
| `deployment.puml` | §2.4.3 Deployment (baru; 2 halaman) |

## Render ke PNG
- **VS Code:** ekstensi *PlantUML* (jebbs) → buka file → `Alt+D` untuk pratinjau, *Export Current Diagram* untuk PNG.
- **CLI:** `brew install plantuml graphviz` lalu `plantuml -tpng docs/diagrams/*.puml`.
- **Docker:** `docker run --rm -v "$PWD/docs/diagrams:/data" plantuml/plantuml -tpng /data/*.puml`.

Diagram ditulis dari kode pada commit saat ini; perbarui bila endpoint, model, atau alur berubah.
