mod omlsa;
mod spectralnoisereduction;

use pyo3::prelude::*;
use numpy::{PyArray1, PyReadonlyArray1, PyArrayMethods};
use omlsa::OmlsaNoiseReduction as RustOmlsaNR;
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

/// OM-LSA / IMCRA noise reduction ("NR2"). The output has the same length
/// as the input and is delayed by `latency` samples.
#[pyclass]
struct OmlsaNoiseReduction {
    inner: RustOmlsaNR,
}

#[pymethods]
impl OmlsaNoiseReduction {
    #[new]
    #[pyo3(signature = (sample_rate, gain_floor_db=-25.0))]
    fn new(sample_rate: u32, gain_floor_db: f32) -> Self {
        Self {
            inner: RustOmlsaNR::new(sample_rate, gain_floor_db),
        }
    }

    #[getter]
    fn latency(&self) -> usize {
        self.inner.latency()
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
    m.add_class::<OmlsaNoiseReduction>()?;
    Ok(())
}
