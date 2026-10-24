mod spectralnoisereduction;

use pyo3::prelude::*;
use numpy::{PyArray1, PyReadonlyArray1, PyArrayMethods};
use spectralnoisereduction::SpectralNoiseReduction as RustSpectralNR;

#[pyclass]
struct SpectralNoiseReduction {
    inner: RustSpectralNR,
}

#[pymethods]
impl SpectralNoiseReduction {
    #[new]
    fn new(sample_rate: u32, gain: f32, alpha: f32, asnr: f32) -> Self {
        Self {
            inner: RustSpectralNR::new(sample_rate, gain, alpha, asnr),
        }
    }
    
    fn process<'py>(
        &mut self,
        py: Python<'py>,
        audio: PyReadonlyArray1<f32>
    ) -> Bound<'py, PyArray1<f32>> {
        let mut data = audio.to_vec().unwrap();
        self.inner.process(&mut data);
        PyArray1::from_vec(py, data)
    }
}

#[pymodule]
fn spectral_nr(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SpectralNoiseReduction>()?;
    Ok(())
}
