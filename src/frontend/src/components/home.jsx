import React from 'react';
// Swiper imports
import { Swiper, SwiperSlide } from 'swiper/react';
import { Pagination, Autoplay, EffectCoverflow } from 'swiper/modules';
// Swiper styles
import 'swiper/css';
import 'swiper/css/effect-coverflow';
import 'swiper/css/pagination';
// Data Visualization Component
import DataVisualization from './DataVisualization';

const Home = () => {
  // 3 slides - order for center view
  const slides = [
    '/img/banner2.png',  // Will be CENTER
    '/img/banner1.png',  // Will be RIGHT
    '/img/banner3.png',  // Will be LEFT (wraps from loop)
  ];

  return (
    <section id="home-page" className="active">
      <div className="section-content">
        {/* 3D Coverflow Banner Slider */}
        <div className="coverflow-banner-container">
          <Swiper
            effect="coverflow"
            grabCursor={true}
            centeredSlides={true}
            slidesPerView="auto"
            initialSlide={2}
            loop={true}
            speed={600}
            coverflowEffect={{
              rotate: 50,
              stretch: 0,
              depth: 100,
              modifier: 1,
              slideShadows: true,
            }}
            autoplay={{
              delay: 4000,
              disableOnInteraction: false,
            }}
            pagination={{
              clickable: true,
              dynamicBullets: true,
            }}
            modules={[EffectCoverflow, Pagination, Autoplay]}
            className="coverflow-swiper"
          >
            {slides.map((slide, index) => (
              <SwiperSlide key={index} className="coverflow-slide">
                <img src={slide} alt={`Banner ${index + 1}`} />
              </SwiperSlide>
            ))}
          </Swiper>
        </div>

        {/* Status Bar */}
        <div className="status-bar animate-card" style={{ animationDelay: '0.05s' }}>
          <div className="status-icon-bg">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
          </div>
          <div className="status-info">
            <h3>Status</h3>
            <p>เครื่องของคุณปลอดภัยดี</p>
          </div>
          <div className="status-action">
            <span>ดูรายละเอียด</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </div>
        </div>

        {/* Summary + Data Visualization (Combined) */}
        <DataVisualization />
      </div>
    </section>
  );
};

export default Home;
