// 后端地址配置。看板所有数据都从这个地址（FastAPI）取。
// 生产：走 nginx 同源路径 /quant-api（nginx 反代到 127.0.0.1:8000），不暴露端口。
// 本地开发：ng serve 时可临时改回 'http://localhost:8000'。
export const environment = {
  apiBaseUrl: '/quant-api',
};
