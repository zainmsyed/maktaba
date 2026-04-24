import { env } from '$env/dynamic/public';

export const load = () => {
  return {
    apiUrl: env.PUBLIC_API_URL || 'http://localhost:8000'
  };
};
