import { Children, useLayoutEffect, useRef } from 'react';
import { communityMasonryLayout } from '../../utils/communityMasonry';

export default function CommunityFeed({ children }) {
    const feed = useRef(null);
    useLayoutEffect(() => {
        const element = feed.current;
        const items = Array.from(element.children);
        let frame;
        const layout = () => {
            // Remove old explicit columns before measuring a narrower breakpoint.
            // Otherwise an old column can survive as an implicit grid track.
            items.forEach(item => { item.style.gridArea = ''; });
            const styles = getComputedStyle(element);
            const columns = styles.gridTemplateColumns.split(' ').length;
            const positions = communityMasonryLayout(items.map(item => item.firstElementChild.getBoundingClientRect().height), columns);
            positions.forEach(({ row, column, span }, index) => {
                items[index].style.gridArea = `${row} / ${column} / span ${span}`;
            });
        };
        layout();
        // Covers late image/font loads, edited content and sidebar/viewport resizing.
        const observer = new ResizeObserver(() => {
            cancelAnimationFrame(frame);
            frame = requestAnimationFrame(layout);
        });
        items.forEach(item => observer.observe(item.firstElementChild));
        return () => { observer.disconnect(); cancelAnimationFrame(frame); };
    }, [children]);

    return <div className="social-feed" ref={feed}>
        {Children.map(children, child => <div className="community-feed-item">{child}</div>)}
    </div>;
}
