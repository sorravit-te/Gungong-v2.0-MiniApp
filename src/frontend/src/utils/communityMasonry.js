// Keep source order, placing each next post in the shortest available column.
export function communityMasonryLayout(heights, columns, rowHeight = 4, gap = 16) {
    const nextRows = Array.from({ length: columns }, () => 1);
    return heights.map(height => {
        const row = Math.min(...nextRows);
        const column = nextRows.indexOf(row);
        const span = Math.max(1, Math.ceil((height + gap) / rowHeight));
        nextRows[column] += span;
        return { row, column: column + 1, span };
    });
}
