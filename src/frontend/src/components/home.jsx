import React, { useRef, useState } from 'react';
// Swiper imports
import { Swiper, SwiperSlide } from 'swiper/react';
import { Autoplay, EffectCoverflow } from 'swiper/modules';
// Swiper styles
import 'swiper/css';
import 'swiper/css/effect-coverflow';
// Data Visualization Component
import DataVisualization from './DataVisualization';

const Home = ({ onNavigate }) => {
  // Stable slide order; the active image is always centred.
  const slides = [
    '/img/banner2.png',
    '/img/banner1.png',
    '/img/banner3.png',
  ];
  // Swiper needs more than three physical slides to loop three visible slots.
  // Three copies allow wraparound without starving the next/previous neighbour.
  const loopSlides = [...slides, ...slides, ...slides];
  const swiperRef = useRef(null);
  const [activeBanner, setActiveBanner] = useState(0);

  return (
    <section id="home-page" className="active">
      <div className="section-content">
        {/* 3D Coverflow Banner Slider */}
        <div className="coverflow-banner-container">
          <Swiper
            effect="coverflow"
            grabCursor={true}
            centeredSlides={true}
            slidesPerView={3}
            initialSlide={3}
            loop={true}
            onSwiper={swiper => { swiperRef.current = swiper; }}
            onSlideChange={swiper => setActiveBanner(swiper.realIndex % slides.length)}
            observer={true}
            observeParents={true}
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
            modules={[EffectCoverflow, Autoplay]}
            className="coverflow-swiper"
          >
            {loopSlides.map((slide, index) => (
              <SwiperSlide key={index} className="coverflow-slide">
                <img src={slide} alt={`Banner ${index % slides.length + 1}`} />
              </SwiperSlide>
            ))}
          </Swiper>
          <div className="banner-pagination" aria-label="เลือกแบนเนอร์">
            {slides.map((slide, index) => <button key={slide} type="button"
              aria-label={`แบนเนอร์ ${index + 1}`} aria-pressed={activeBanner === index}
              className={activeBanner === index ? 'active' : ''}
              onClick={() => {
                const swiper = swiperRef.current;
                if (!swiper) return;
                // Choose the same group of three so a bullet only moves 1–2 slides.
                const group = Math.floor(swiper.realIndex / slides.length) * slides.length;
                swiper.slideToLoop(group + index);
              }} />)}
          </div>
        </div>

        {/* Summary + Data Visualization (Combined) */}
        <DataVisualization onNavigate={onNavigate} />
      </div>
    </section>
  );
};

export default Home;
