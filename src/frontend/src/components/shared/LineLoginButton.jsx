import { useAuth } from '../../contexts/AuthContext';

const LineLoginButton = ({ currentPage = 'home', className = '' }) => {
  const { signInWithLine, lineLoading } = useAuth();
  const login = async () => {
    const result = await signInWithLine({ section: currentPage });
    if (!result.success) window.Swal?.fire({ icon: 'info', title: 'เข้าสู่ระบบ LINE',
      text: result.error, confirmButtonColor: '#06C755' });
  };
  return <button type="button" className={`line-login-btn ${className}`} onClick={login}
    disabled={lineLoading} aria-label="เข้าสู่ระบบด้วย LINE" title="เข้าสู่ระบบด้วย LINE">
    <svg className="line-login-mark" viewBox="0 0 40 40" aria-hidden="true">
      <path fill="currentColor" d="M35 18c0-7.2-6.7-13-15-13S5 10.8 5 18c0 6.5 5.4 11.9 12.6 12.9.5.1 1.2.3 1.3.7.2.4.1 1.1.1 1.5l-.2 1.3c-.1.4-.4 1.7 1.5.9 1.9-.8 10.3-6 13.9-10.3C36.7 21.8 35 18 35 18Z" />
      <text x="20" y="21.5" textAnchor="middle" fill="#06C755" fontSize="9" fontWeight="800" fontFamily="Arial, sans-serif">LINE</text>
    </svg>
  </button>;
};

export default LineLoginButton;
