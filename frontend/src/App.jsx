import { useEffect, useState } from 'react';
import api from './api/axios';

export default function App() {
  const [message, setMessage] = useState('로딩 중...');

  useEffect(() => {
    api.get('/api/test')
        .then((res) => {
          setMessage(res.data);
        })
        .catch((err) => {
          console.error('백엔드 통신 에러:', err);
          setMessage('서버 연결 실패');
        });
  }, []);

  return (
      <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-6">
        {message}
      </div>
  );
}