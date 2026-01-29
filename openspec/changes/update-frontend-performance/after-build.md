# After build (update-frontend-performance)

Дата: 2026-01-29
Коммит (base): 86185c9669f9892633334508abdef3435017defb

Команда:
```bash
cd frontend && npm run build
```

Вывод (vite chunk sizes):
```
dist/index.html                                     1.68 kB │ gzip:   0.60 kB
dist/assets/editor.worker-CKy7Pnvo.js             252.39 kB
dist/assets/json.worker-usMZ-FED.js               384.42 kB
dist/assets/WorkflowList-DnaWheGb.css               0.23 kB │ gzip:   0.17 kB
dist/assets/JsonCodeEditor-ODv6FwRF.css             0.38 kB │ gzip:   0.24 kB
dist/assets/index-YQAUdu0W.css                      0.40 kB │ gzip:   0.28 kB
dist/assets/WorkflowExecutions-CXwXEaFv.css         1.19 kB │ gzip:   0.41 kB
dist/assets/WorkflowDesigner-DfRg28kM.css           1.44 kB │ gzip:   0.56 kB
dist/assets/WorkflowMonitor-BTAqKEKw.css            2.09 kB │ gzip:   0.77 kB
dist/assets/useServiceMesh-B5KtklQx.css             2.98 kB │ gzip:   0.72 kB
dist/assets/OperationTimelineDrawer-DFiKa3Jt.css    4.58 kB │ gzip:   1.30 kB
dist/assets/ServiceMeshPage-DpqeFnhG.css            6.65 kB │ gzip:   1.72 kB
dist/assets/reactflow-B5DZHykP.css                  7.32 kB │ gzip:   1.60 kB
dist/assets/workflowTransforms-BpxnD6RH.css        10.21 kB │ gzip:   2.60 kB
dist/assets/reactflow-BP6UHo6r.js                   0.08 kB │ gzip:   0.09 kB │ map:     0.10 kB
dist/assets/monacoEnv-uDUlUzlq.js                   0.20 kB │ gzip:   0.18 kB │ map:     0.88 kB
dist/assets/runtimeSettings-D9B91WEl.js             0.32 kB │ gzip:   0.24 kB │ map:     1.17 kB
dist/assets/databaseStatus-LEMwDqoX.js              0.56 kB │ gzip:   0.25 kB │ map:     2.57 kB
dist/assets/operations-DqBzvUG3.js                  0.71 kB │ gzip:   0.30 kB │ map:     7.98 kB
dist/assets/ForbiddenPage-DD7MExbS.js               0.72 kB │ gzip:   0.53 kB │ map:     1.05 kB
dist/assets/driverCommands-BsbbG8Cs.js              0.98 kB │ gzip:   0.54 kB │ map:     5.31 kB
dist/assets/LazyJsonCodeEditor-dDQgQt7A.js          1.51 kB │ gzip:   0.73 kB │ map:     2.36 kB
dist/assets/zustand-DbHDWmdh.js                     1.57 kB │ gzip:   0.82 kB │ map:     6.90 kB
dist/assets/JsonCodeEditor-CBY8QtMp.js              1.94 kB │ gzip:   1.03 kB │ map:     5.05 kB
dist/assets/clusters-BpQwYZt6.js                    2.42 kB │ gzip:   0.95 kB │ map:    11.89 kB
dist/assets/Login-BiOBEMHf.js                       2.49 kB │ gzip:   1.45 kB │ map:     7.19 kB
dist/assets/timelineTransforms-DwTV_jlL.js          2.64 kB │ gzip:   0.95 kB │ map:     7.10 kB
dist/assets/artifacts-BIhly2Kh.js                   2.69 kB │ gzip:   0.91 kB │ map:    14.38 kB
dist/assets/WorkflowList-AWPL6Lc1.js                4.45 kB │ gzip:   1.80 kB │ map:    12.40 kB
dist/assets/RuntimeSettingsPage-BK35ohRM.js         5.13 kB │ gzip:   2.32 kB │ map:    15.88 kB
dist/assets/DLQPage-D7Zsm20N.js                     5.98 kB │ gzip:   2.65 kB │ map:    18.12 kB
dist/assets/TimelineSettingsPage-B3h-T26h.js        6.08 kB │ gzip:   2.69 kB │ map:    18.94 kB
dist/assets/Extensions-BwKXjaad.js                  6.71 kB │ gzip:   2.38 kB │ map:    22.67 kB
dist/assets/databases-CuX7KbLD.js                   6.78 kB │ gzip:   1.39 kB │ map:    28.29 kB
dist/assets/WorkflowExecutions-BqT47YtD.js          7.23 kB │ gzip:   2.75 kB │ map:    22.34 kB
dist/assets/WorkflowDesigner-Byjz5kTM.js            7.28 kB │ gzip:   2.71 kB │ map:    24.06 kB
dist/assets/UsersPage-dqIjfNFZ.js                   7.44 kB │ gzip:   2.51 kB │ map:    22.92 kB
dist/assets/SystemStatus-COmem3_c.js                7.55 kB │ gzip:   3.31 kB │ map:    25.65 kB
dist/assets/OperationTimelineDrawer-kqW4241G.js     7.95 kB │ gzip:   2.96 kB │ map:    28.07 kB
dist/assets/TemplatesPage-iqeFL5bv.js               8.40 kB │ gzip:   3.17 kB │ map:    25.99 kB
dist/assets/useServiceMesh-Bf7VnmdG.js              9.87 kB │ gzip:   3.56 kB │ map:    37.14 kB
dist/assets/Dashboard--38duXJT.js                  11.44 kB │ gzip:   4.49 kB │ map:    54.01 kB
dist/assets/monaco-geGS74Jl.js                     12.22 kB │ gzip:   4.60 kB │ map:    37.33 kB
dist/assets/OperationsPage-BElznoRw.js             13.72 kB │ gzip:   5.05 kB │ map:    50.72 kB
dist/assets/WorkflowMonitor-Cu2N-7L0.js            15.23 kB │ gzip:   5.44 kB │ map:    58.23 kB
dist/assets/Clusters-DUQXHCn-.js                   15.80 kB │ gzip:   4.98 kB │ map:    55.33 kB
dist/assets/ServiceMeshPage-DqfezCls.js            16.95 kB │ gzip:   6.03 kB │ map:    66.74 kB
dist/assets/Databases-Bx58TAE_.js                  24.68 kB │ gzip:   8.70 kB │ map:    91.04 kB
dist/assets/antd-select-rdoRxV7d.js                24.69 kB │ gzip:   6.77 kB │ map:    88.10 kB
dist/assets/antd-form-L_nqr-xf.js                  25.95 kB │ gzip:   8.97 kB │ map:   113.05 kB
dist/assets/ArtifactsPage-J7xWnJHy.js              26.89 kB │ gzip:   9.44 kB │ map:    99.08 kB
dist/assets/antd-date-Brb7ecrV.js                  28.47 kB │ gzip:   8.07 kB │ map:   103.83 kB
dist/assets/useTableToolkit-CfmLjrhu.js            29.15 kB │ gzip:   9.23 kB │ map:   120.93 kB
dist/assets/ActionCatalogPage-DgJelkf7.js          29.17 kB │ gzip:   9.76 kB │ map:   102.43 kB
dist/assets/axios-ngrFHoWO.js                      36.05 kB │ gzip:  14.59 kB │ map:   170.94 kB
dist/assets/DriverCommandBuilder-DkplqESE.js       38.54 kB │ gzip:  11.74 kB │ map:   144.50 kB
dist/assets/workflowTransforms--LAW4OeG.js         40.02 kB │ gzip:  10.95 kB │ map:   160.34 kB
dist/assets/tanstack-CEo9_Z5g.js                   40.45 kB │ gzip:  12.06 kB │ map:   152.02 kB
dist/assets/antd-overlay-DFhvX__s.js               41.12 kB │ gzip:  12.38 kB │ map:   162.60 kB
dist/assets/antd-table-DpTZY6HJ.js                 51.16 kB │ gzip:  16.64 kB │ map:   216.13 kB
dist/assets/OperationTimelineDrawer-OcYBlaWL.js    59.79 kB │ gzip:  18.70 kB │ map:   248.71 kB
dist/assets/CommandSchemasPage-B-uxpxbS.js         61.61 kB │ gzip:  15.14 kB │ map:   201.39 kB
dist/assets/index-B89hyYiK.js                      70.98 kB │ gzip:  16.52 kB │ map:   320.37 kB
dist/assets/ant-design-LmN7pFUG.js                112.18 kB │ gzip:  35.13 kB │ map:   495.67 kB
dist/assets/RBACPage-8gxN-lZ8.js                  135.17 kB │ gzip:  28.88 kB │ map:   461.31 kB
dist/assets/react-hvTa2sJv.js                     155.04 kB │ gzip:  50.11 kB │ map:   488.64 kB
dist/assets/charts-BmRr_ANi.js                    305.26 kB │ gzip:  87.07 kB │ map: 1,402.38 kB
dist/assets/rc-GEfmiyK0.js                        441.73 kB │ gzip: 148.19 kB │ map: 2,251.03 kB
dist/assets/vendor-Dg6XRWpl.js                    448.12 kB │ gzip: 149.65 kB │ map: 2,211.22 kB
dist/assets/antd-core-CJsywuNd.js                 483.38 kB │ gzip: 131.07 kB │ map: 1,766.62 kB
```
