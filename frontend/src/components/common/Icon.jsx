import React from 'react';
import { icons, ICON_VIEWBOX } from '../../constants/icons';

export default function Icon({ name, className = '', style = {}, ariaHidden = true }) {
  const pathMarkup = icons[name] || icons.file;
  const viewBox = ICON_VIEWBOX[name] || '0 0 24 24';

  return (
    <svg
      className={`ico ${className}`}
      viewBox={viewBox}
      style={style}
      aria-hidden={ariaHidden}
      dangerouslySetInnerHTML={{ __html: pathMarkup }}
    />
  );
}
