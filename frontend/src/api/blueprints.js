import client from './client';

export const getBlueprints = () => client.get('/blueprints');
export const getBlueprintById = (id) => client.get(`/blueprints/${id}`);
export const createBlueprint = (data) => client.post('/blueprints', data);
export const updateBlueprint = (id, data) => client.put(`/blueprints/${id}`, data);
export const deleteBlueprint = (id) => client.delete(`/blueprints/${id}`);
export const duplicateBlueprint = (id) => client.post(`/blueprints/${id}/duplicate`);